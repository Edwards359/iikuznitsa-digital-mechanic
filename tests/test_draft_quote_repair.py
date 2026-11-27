"""Черновик заявки: пересказанная цитата чинится дословным фрагментом со страницы."""

from app.agent import Consultant


def test_draft_repairs_paraphrased_quote(monkeypatch) -> None:
    engine = "ЯМЗ-236М2"
    page_body = (
        "Перед регулировкой зазора клапанов двигатель должен быть холодным. "
        "Проверить тепловой зазор впускных и выпускных клапанов."
    )

    class SearchStub:
        def ready(self) -> bool:
            return True

        def page_text(self, eng: str, manual: str, page: int) -> str | None:
            if eng == engine and page == 2:
                return page_body
            return None

    c = Consultant(SearchStub())
    vehicle = {
        "vehicle_id": "v1",
        "engine_model": engine,
        "sessions": [{"session_id": "s1", "status": "anomaly", "anomaly_type": "F08"}],
    }
    args = {
        "session_id": "s1",
        "conclusion": "Отклонение по клапанам",
        "operations": ["Проверить тепловой зазор клапанов"],
        "references": [
            {
                "manual": "236.01.01 РК",
                "pdf_page": 2,
                "quote": "нужно отрегулировать клапаны на холодном моторе",
            }
        ],
    }

    monkeypatch.setattr(
        "app.agent._local_check",
        lambda _v, sid: {"session_id": sid, "anomaly_type": "F08"},
    )
    monkeypatch.setattr(
        "app.agent._diagnose",
        lambda _vid, _sid: {
            "status": "anomaly",
            "anomaly_type": "F08",
            "signal_quality": "good",
            "confidence": 0.9,
            "anomaly_score": 0.7,
        },
    )
    monkeypatch.setattr(
        "app.agent.store.save_draft",
        lambda vehicle_id, session_id, payload, reason: {
            "draft_id": "d1",
            "vehicle_id": vehicle_id,
            "session_id": session_id,
            "payload": payload,
            "reason": reason,
        },
    )

    result, draft = c._draft(args, vehicle, engine)
    assert draft is not None
    assert "error" not in result
    assert "дословным" in (result.get("note") or "")
