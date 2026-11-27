from app import store
from app.agent import confirm_draft


def test_confirm_allows_urgency_override(monkeypatch) -> None:
    payload = {
        "vehicle_id": "V1",
        "session_id": "S1",
        "anomaly_type": "F01",
        "conclusion": "Тест",
        "urgency": "low",
        "operations": ["Работа"],
        "spare_parts": [],
        "references": [{"manual": "236.01.01 РК", "pdf_page": 2}],
    }
    saved = store.save_draft("V1", "S1", payload, "причина")
    draft_id = saved["draft_id"]

    class Resp:
        status_code = 201

        @staticmethod
        def json() -> dict:
            return {"ticket_id": "TKT-0099", "status": "created"}

    monkeypatch.setattr("app.agent.httpx.post", lambda *a, **k: Resp())

    out = confirm_draft(draft_id, urgency="high")
    assert out.get("ticket_id") == "TKT-0099"
    draft = store.get_draft(draft_id)
    assert draft is not None
    assert draft["payload"]["urgency"] == "high"