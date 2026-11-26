from app.agent import Consultant, verify_citations
from app.catalog import demo_sessions, get_vehicle, vehicles
from app.manuals import manuals_for
from app.priority import choose_urgency
from app.rag import chunk_text


class _Pages:
    def page_text(self, engine: str, manual: str, page: int) -> str | None:
        if engine == "ЯМЗ-236М2" and page == 2:
            return "Проверить зазор клапанов на холодном двигателе"
        return None


def test_park_size() -> None:
    assert len(vehicles()) == 50


def test_demo_sessions_cover_failure_and_engines() -> None:
    rows = demo_sessions()
    labels = " ".join(row["label"] for row in rows)
    assert "сбой записи" in labels.casefold()
    assert labels.count("Отклонение") >= 4


def test_manuals_do_not_cross_engines() -> None:
    yamz = {item.manual_id for item in manuals_for("ЯМЗ-236М2")}
    zmz = {item.manual_id for item in manuals_for("ЗМЗ-5234.10")}
    assert yamz.isdisjoint(zmz)
    assert len(manuals_for("ЗМЗ-40905.10")) == 1
    assert manuals_for("ЗМЗ-40905.10") == manuals_for("ЗМЗ-40904.10")


def test_priority_rules() -> None:
    rising = [
        {"status": "anomaly", "anomaly_type": "F01", "anomaly_score": 0.41},
        {"status": "anomaly", "anomaly_type": "F01", "anomaly_score": 0.58},
        {"status": "anomaly", "anomaly_type": "F01", "anomaly_score": 0.77},
    ]
    current = {
        "status": "anomaly",
        "anomaly_type": "F01",
        "anomaly_score": 0.77,
        "confidence": 0.8,
        "signal_quality": "good",
    }
    assert choose_urgency(rising, current)[0] == "high"
    noisy = {**current, "signal_quality": "warning", "confidence": 0.9, "anomaly_score": 0.93}
    assert choose_urgency([noisy], noisy)[0] == "low"
    weak = {**current, "anomaly_score": 0.6, "confidence": 0.8}
    assert choose_urgency([weak], weak)[0] == "low"


def test_unknown_quote_is_removed() -> None:
    text = "Сделайте так: «этой фразы нет» (236.01.01 РК, стр. 2)."
    cleaned = verify_citations(text, _Pages(), "ЯМЗ-236М2")
    assert "этой фразы нет" not in cleaned
    assert "снята" in cleaned


def test_known_quote_stays() -> None:
    text = "«Проверить зазор клапанов» (236.01.01 РК, стр. 2)."
    assert verify_citations(text, _Pages(), "ЯМЗ-236М2") == text


def test_chunks_cover_long_page() -> None:
    parts = chunk_text(("абзац про масло\n" * 80).strip())
    assert len(parts) > 1
    assert all(parts)


def test_check_failed_skips_model(monkeypatch) -> None:
    vehicle = next(
        item
        for item in vehicles()
        for session in item["sessions"]
        if session["status"] == "check_failed"
    )
    session = next(item for item in vehicle["sessions"] if item["status"] == "check_failed")

    def fake_diagnose(vehicle_id: str, session_id: str) -> dict:
        assert vehicle_id == vehicle["vehicle_id"]
        return {
            "vehicle_id": vehicle_id,
            "session_id": session_id,
            "status": "check_failed",
            "anomaly_type": None,
            "anomaly_title": None,
            "anomaly_score": None,
            "confidence": None,
            "signal_quality": "bad",
            "description": "запись сорвана",
            "model_version": "mock-v1",
        }

    monkeypatch.setattr("app.agent._diagnose", fake_diagnose)
    monkeypatch.setattr(
        "app.agent.llm.complete",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model must not run")),
    )
    result = Consultant().run(vehicle["vehicle_id"], "разбери", session["session_id"])
    assert "Сбой проверки" in result["answer"]
    assert result["draft"] is None
    assert get_vehicle(vehicle["vehicle_id"]) is not None
