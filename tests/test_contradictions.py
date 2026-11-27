from app.contradictions import contradiction_hints


def test_no_hints_without_keywords() -> None:
    assert contradiction_hints("ЯМЗ-236М2", "проверить давление масла") == []


def test_yamz_valve_hints() -> None:
    rows = contradiction_hints("ЯМЗ-236М2", "регулировка зазора клапанов")
    assert len(rows) == 1
    assert rows[0]["sources"][0]["page"] == 31