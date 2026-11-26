"""Веб-чат и API. Заглушки заказчика — отдельные процессы."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import catalog, llm
from app.agent import Consultant, confirm_draft
from app.config import LLM_PROVIDER, VOICE_STT_ENABLED, YANDEX_API_KEY, YANDEX_RUB_PER_KTOK
from app import store
from app.manuals import manuals_for
from app import stt
from app.languages import ANSWER_LANGUAGES, answer_lang_prefix
from app.rag import ManualSearch, render_page_png

STATIC = Path(__file__).resolve().parents[1] / "static"
search = ManualSearch()
consultant = Consultant(search)

app = FastAPI(title="Цифровой механик", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class ConsultRequest(BaseModel):
    vehicle_id: str = Field(min_length=1)
    session_id: str | None = None
    message: str = ""
    # ru по умолчанию; отдельных языковых моделей нет — только промпт к той же LLM
    lang: str = Field(default="ru", max_length=8)


@app.get("/api/languages")
def languages() -> list[dict]:
    labels = {
        "ru": "Русский (основной)",
        "uk": "Українська",
        "be": "Беларуская",
        "kk": "Қазақша",
        "uz": "Oʻzbek",
        "ky": "Кыргызча",
        "tg": "Тоҷикӣ",
        "hy": "Հայերեն",
        "az": "Azərbaycanca",
        "ka": "ქართული",
        "ro": "Română",
        "hi": "हिन्दी",
    }
    return [{"code": code, "label": labels.get(code, code)} for code in ANSWER_LANGUAGES]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    vec = search.vector_stats()
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "model": llm.model_name(),
        "index_chunks": len(search.chunks),
        "search_hybrid": search.hybrid_ready(),
        "embedding_vectors": vec["count"],
        "embedding_dim": vec["dim"],
        "vehicles": len(catalog.vehicles()),
        "voice_stt": "yandex" if (VOICE_STT_ENABLED and YANDEX_API_KEY) else "none",
    }


@app.get("/api/voice/status")
def voice_status() -> dict:
    if not VOICE_STT_ENABLED:
        return {
            "engine": "none",
            "enabled": False,
            "reason": "Платный SpeechKit отключён: см. docs/VOICE-ROADMAP.md",
            "walkthrough_keys": ["ArrowLeft", "ArrowRight"],
        }
    return {
        "engine": "yandex" if YANDEX_API_KEY else "none",
        "enabled": bool(YANDEX_API_KEY),
        "wake_word": "помощник",
    }


@app.post("/api/voice")
async def voice_recognize(request: Request) -> dict:
    if not VOICE_STT_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Распознавание по API отключено. Пошаговый ремонт — клавиши ← →.",
        )
    mime = request.headers.get("content-type", "application/octet-stream")
    data = await request.body()
    if len(data) < 80:
        return {"text": ""}
    try:
        text = stt.recognize(data, mime)
    except stt.SttError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"text": text}


@app.get("/api/vehicles")
def list_vehicles() -> list[dict]:
    return [catalog.public_vehicle(item) for item in catalog.vehicles()]


def _rub_from_usage(usage: dict) -> float | None:
    if LLM_PROVIDER != "yandex":
        return None
    tokens = int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
    return round(tokens * YANDEX_RUB_PER_KTOK / 1000, 2)


@app.get("/api/vehicles/{vehicle_id}")
def vehicle_card(vehicle_id: str) -> dict:
    vehicle = catalog.get_vehicle(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="машина не найдена")
    engine = vehicle.get("engine_model") or ""
    manuals = [{"manual_id": item.manual_id, "filename": item.filename} for item in manuals_for(engine)]
    card = catalog.public_vehicle(vehicle)
    card["manuals"] = manuals
    tickets = store.history(vehicle_id)
    consults = store.consultations(vehicle_id)
    usage = store.usage_totals(vehicle_id)
    return {
        "vehicle": card,
        "tickets": tickets,
        "consultations": consults,
        "usage": usage,
    }


@app.get("/api/usage/summary")
def usage_summary() -> dict:
    """Сводка консультаций из SQLite (для демо экономики)."""
    totals = store.usage_totals()
    totals["provider"] = LLM_PROVIDER
    totals["model"] = llm.model_name()
    totals["rub_per_ktok_note"] = (
        f"оценка ₽: {YANDEX_RUB_PER_KTOK} за 1k токенов (YandexGPT Pro 5, AI Studio 2026-11-26)"
        if LLM_PROVIDER == "yandex"
        else None
    )
    return totals


@app.get("/api/demo-sessions")
def list_demo_sessions() -> list[dict]:
    return catalog.demo_sessions()


@app.get("/api/quick-checks")
def list_quick_checks() -> list[dict]:
    """Те же проверки, что и demo-sessions; имя без слова «демо» для интерфейса."""
    return catalog.demo_sessions()


@app.get("/api/page-image")
def page_image(manual: str = Query(min_length=1), page: int = Query(ge=1)) -> Response:
    blob = render_page_png(manual, page)
    if blob is None:
        raise HTTPException(status_code=404, detail="страница не найдена")
    return Response(content=blob, media_type="image/png")


@app.post("/api/consult")
def consult(body: ConsultRequest) -> dict:
    lang = body.lang if body.lang in ANSWER_LANGUAGES else "ru"
    text = body.message.strip() or (
        "Разбери проверку: сам найди процедуру в РК и веди механика по шагам ремонта; "
        "при отклонении подготовь черновик заявки."
    )
    prefix = answer_lang_prefix(lang)
    result = consultant.run(body.vehicle_id, f"{prefix}{text}", body.session_id)
    usage = result.get("usage") or {}
    steps = result.get("steps") or []
    repair_steps = result.get("repair_steps") or []
    used_llm = bool(usage.get("input_tokens") or usage.get("output_tokens"))
    store.save_consultation(
        body.vehicle_id,
        body.session_id,
        model=llm.model_name() if used_llm else "rules",
        provider=LLM_PROVIDER if used_llm else "rules",
        usage=usage,
        steps=steps,
        answer=result.get("answer") or "",
        error=result.get("error"),
        has_draft=bool(result.get("draft")),
        repair_steps=len(repair_steps),
        cost_rub=_rub_from_usage(usage),
    )
    return result


@app.post("/api/drafts/{draft_id}/confirm")
def confirm(draft_id: str) -> dict:
    out = confirm_draft(draft_id)
    return out
