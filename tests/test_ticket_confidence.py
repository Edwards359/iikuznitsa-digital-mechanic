from app.agent import Consultant
from app.config import MIN_TICKET_CONFIDENCE


def test_draft_blocked_below_min_confidence(monkeypatch) -> None:
    engine = "ЯМЗ-236М2"

    class SearchStub:
        def ready(self) -> bool:
            return True

        def page_text(self, eng: str, manual: str, page: int) -> str | None:
            return "Проверить давление масла" if eng == engine and page == 2 else None

    c = Consultant(SearchStub())
    vehicle = {
        "vehicle_id": "v1",
        "engine_model": engine,
        "sessions": [{"session_id": "s1"}],
    }
    args = {
        "session_id": "s1",
        "conclusion": "Тест",
        "operations": ["Шаг 1"],
        "references": [{"manual": "236.01.01 РК", "pdf_page": 2, "quote": "давление масла"}],
    }

    monkeypatch.setattr(
        "app.agent._local_check",
        lambda _vid, sid: {"session_id": sid, "anomaly_type": "F01"},
    )
    monkeypatch.setattr(
        "app.agent._diagnose",
        lambda _vid, _sid: {
            "status": "anomaly",
            "anomaly_type": "F01",
            "signal_quality": "good",
            "confidence": MIN_TICKET_CONFIDENCE - 0.01,
        },
    )

    result, draft = c._draft(args, vehicle, engine)
    assert draft is None
    assert "error" in result