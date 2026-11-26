"""Веб-чат и API. Заглушки заказчика — отдельные процессы."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import catalog, llm
from app.agent import Consultant, confirm_draft
from app.config import LLM_PROVIDER
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
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "model": llm.model_name(),
        "index_chunks": len(search.chunks),
        "vehicles": len(catalog.vehicles()),
    }


@app.get("/api/vehicles")
def list_vehicles() -> list[dict]:
    return [catalog.public_vehicle(item) for item in catalog.vehicles()]


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
    return consultant.run(body.vehicle_id, f"{prefix}{text}", body.session_id)


@app.post("/api/drafts/{draft_id}/confirm")
def confirm(draft_id: str) -> dict:
    return confirm_draft(draft_id)
