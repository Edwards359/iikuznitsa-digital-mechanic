"""Веб-чат и API. Заглушки заказчика — отдельные процессы."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import catalog, llm
from app.agent import (
    Consultant,
    confirm_draft,
    diagnose_check,
    fault_spare_query,
    is_part_label,
)
from app.config import (
    LLM_PROVIDER,
    LOW_CONFIDENCE,
    MIN_TICKET_CONFIDENCE,
    VOICE_MODE,
    YANDEX_API_KEY,
    YANDEX_RUB_PER_KTOK,
)
from app.contradictions import contradiction_hints
from app import store
from app.manuals import manual_by_id, manuals_for
from app import stt
from app.languages import ANSWER_LANGUAGES, answer_lang_prefix
from app.rag import ManualSearch, is_contents_page, render_page_png
from app.web_parts import internet_spare_candidates

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


class ConfirmDraftRequest(BaseModel):
    urgency: Literal["low", "medium", "high"] | None = None


class SparePartsRequest(BaseModel):
    vehicle_id: str = Field(min_length=1)
    session_id: str | None = None
    query: str = ""


class DraftSparesRequest(BaseModel):
    spare_parts: list[str] = Field(default_factory=list)


class BuildDraftRequest(BaseModel):
    vehicle_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    answer: str = ""


class RepairProgressRequest(BaseModel):
    vehicle_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    consult_id: str | None = None
    step_index: int = Field(ge=0)
    step_total: int = Field(ge=0)
    status: str = "in_progress"
    summary: str = ""


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
        "voice_stt": VOICE_MODE,
        "min_ticket_confidence": MIN_TICKET_CONFIDENCE,
        "low_confidence": LOW_CONFIDENCE,
        "priority_meaning": {
            "high": "дефектовка до выпуска в рейс",
            "medium": "дефектовка на ближайшем ТО, под наблюдением",
            "low": "узел проверяется на следующей проверке",
        },
    }


@app.get("/api/voice/status")
def voice_status() -> dict:
    base = {
        "mode": VOICE_MODE,
        "wake_word": "помощник",
        "walkthrough_keys": ["ArrowLeft", "ArrowRight"],
    }
    if VOICE_MODE == "off":
        return {**base, "engine": "none", "enabled": False, "cost": "нет голоса, только клавиши"}
    if VOICE_MODE == "yandex":
        ok = bool(YANDEX_API_KEY)
        return {
            **base,
            "engine": "yandex" if ok else "none",
            "enabled": ok,
            "cost": "SpeechKit: один запрос на нажатие (push-to-talk)",
            "hint": "Удерживайте кнопку микрофона и скажите: Помощник, следующий шаг",
        }
    return {
        **base,
        "engine": "browser",
        "enabled": True,
        "cost": "0 ₽ — распознавание в браузере (Chrome/Edge, HTTPS)",
        "hint": "Помощник, следующий шаг — кодовое слово обязательно",
    }


@app.post("/api/voice")
async def voice_recognize(request: Request) -> dict:
    if VOICE_MODE != "yandex":
        raise HTTPException(
            status_code=503,
            detail="Облачный STT выключен. Режим browser — распознавание в браузере.",
        )
    if not YANDEX_API_KEY:
        raise HTTPException(status_code=503, detail="YANDEX_API_KEY не задан")
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
    progress = store.repair_progress(vehicle_id)
    return {
        "vehicle": card,
        "tickets": tickets,
        "consultations": consults,
        "usage": usage,
        "repair_progress": progress,
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
    known = manual_by_id(manual)
    if known is not None:
        for engine in known.engines:
            body = search.page_text(engine, known.manual_id, page)
            if body and is_contents_page(body):
                raise HTTPException(
                    status_code=404,
                    detail="страница оглавления запрещена для демонстрации",
                )
            if body is not None:
                break
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
    saved = store.save_consultation(
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
    engine = result.get("engine") or (catalog.get_vehicle(body.vehicle_id) or {}).get("engine_model") or ""
    hints = contradiction_hints(engine, f"{text}\n{result.get('answer') or ''}")
    if hints:
        result["contradiction_hints"] = hints
    if body.session_id and repair_steps:
        store.save_repair_progress(
            body.vehicle_id,
            body.session_id,
            consult_id=saved.get("id"),
            step_index=0,
            step_total=len(repair_steps),
            status="in_progress",
            summary=(result.get("answer") or "")[:400],
        )
    result["consultation_id"] = saved.get("id")
    return result


@app.post("/api/repair-progress")
def repair_progress(body: RepairProgressRequest) -> dict:
    return store.save_repair_progress(
        body.vehicle_id,
        body.session_id,
        consult_id=body.consult_id,
        step_index=body.step_index,
        step_total=body.step_total,
        status=body.status,
        summary=body.summary,
    )


@app.post("/api/spare-parts")
def spare_parts_search(body: SparePartsRequest) -> dict:
    """Кандидаты запчастей для выбора: веб-заглушка + подсказки из РЭ/РК.

    Веб-поиск без привязки к магазину/бренду пока демонстрационный, но выбор позиции
    обязателен для заявки.
    """
    vehicle = catalog.get_vehicle(body.vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="машина не найдена")
    engine = vehicle.get("engine_model") or ""
    query = (body.query or "").strip()
    remote = None
    if body.session_id:
        remote = diagnose_check(body.vehicle_id, body.session_id)
        if "error" in remote:
            remote = None
        if not query:
            query = fault_spare_query(remote)
    if not query:
        query = "запчасти ремонт"
    fault_type = (remote or {}).get("anomaly_type")
    fault_title = (remote or {}).get("anomaly_title")
    # Для выбора в UI — только короткие имена деталей (веб-заглушка).
    # Фрагменты РЭ/РК в список не подмешиваем: там часто процессы и чужой двигатель.
    items = [
        row
        for row in internet_spare_candidates(
            query,
            anomaly_type=fault_type,
            anomaly_title=fault_title,
            limit=8,
        )
        if is_part_label(row.get("label") or "")
    ]
    return {
        "query": query,
        "engine": engine,
        "mode": "web_stub",
        "mode_note": (
            "Кандидаты-детали из открытых источников (демо, без магазина и производителя). "
            "Выберите нужные позиции кнопкой «Выбрать» и добавьте в заявку."
        ),
        "fault": {
            "anomaly_type": fault_type,
            "anomaly_title": fault_title,
        },
        "items": items,
    }


@app.post("/api/drafts/build")
def build_draft(body: BuildDraftRequest) -> dict:
    """Принудительно собрать явный черновик заявки при anomaly (без ожидания draft_ticket модели)."""
    draft = consultant.build_anomaly_draft(
        body.vehicle_id,
        body.session_id,
        answer=body.answer or "",
    )
    if draft is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Не удалось собрать черновик: нужна проверка со статусом anomaly, "
                "уверенность ≥ порога и страницы процедуры в РЭ/РК (не оглавление)"
            ),
        )
    return {"draft": draft, "draft_notice": "Черновик собран по кнопке механика."}


@app.post("/api/drafts/{draft_id}/spare-parts")
def draft_add_spares(draft_id: str, body: DraftSparesRequest) -> dict:
    draft = store.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="черновик не найден")
    if draft.get("ticket_id"):
        raise HTTPException(status_code=400, detail="заявка уже отправлена")
    payload = dict(draft["payload"])
    current = [str(item).strip() for item in payload.get("spare_parts") or [] if str(item).strip()]
    from app.agent import is_part_label

    # В заявку — только детали; процессы ремонта отбрасываем.
    current = [item for item in current if is_part_label(item)]
    for label in body.spare_parts or []:
        text = str(label).strip()
        if text and is_part_label(text) and text not in current:
            current.append(text)
    payload["spare_parts"] = current[:12]
    store.update_draft_payload(draft_id, payload)
    refreshed = store.get_draft(draft_id)
    return {"draft": refreshed}


@app.post("/api/drafts/{draft_id}/confirm")
def confirm(draft_id: str, body: ConfirmDraftRequest | None = None) -> dict:
    urgency = body.urgency if body else None
    out = confirm_draft(draft_id, urgency=urgency)
    draft = store.get_draft(draft_id)
    if draft and out.get("ticket_id"):
        store.save_repair_progress(
            draft["vehicle_id"],
            draft["session_id"],
            step_index=0,
            step_total=0,
            status="ticket_submitted",
            summary=f"Заявка {out['ticket_id']}",
        )
    return out
