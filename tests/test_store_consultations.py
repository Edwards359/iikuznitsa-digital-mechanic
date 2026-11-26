"""SQLite: консультации по машине."""

from __future__ import annotations

import os

import pytest

from app import store  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "test.db"
    from app import config

    monkeypatch.setattr(config, "DB_PATH", db)


def test_save_and_list_consultation() -> None:
    store.save_consultation(
        "V-001",
        "S-001",
        model="yandexgpt/latest",
        provider="yandex",
        usage={"input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.01},
        steps=[{"tool": "get_check"}, {"tool": "search_manual"}],
        answer="Тестовый ответ",
        has_draft=True,
        repair_steps=4,
        cost_rub=1.44,
    )
    rows = store.consultations("V-001")
    assert len(rows) == 1
    assert rows[0]["session_id"] == "S-001"
    assert rows[0]["tools"] == ["get_check", "search_manual"]
    assert rows[0]["has_draft"] is True
    totals = store.usage_totals("V-001")
    assert totals["consults"] == 1
    assert totals["input_tokens"] == 1000