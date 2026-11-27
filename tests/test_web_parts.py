from app.web_parts import internet_spare_candidates


def test_internet_candidates_for_clutch_are_selectable() -> None:
    rows = internet_spare_candidates("выжимной подшипник", anomaly_type="F06")
    assert rows
    assert all(row.get("selectable") is True for row in rows)
    assert all(row.get("source") == "web_stub" for row in rows)
    assert any("подшипник" in row["label"].casefold() for row in rows)
    joined = " ".join(row["label"] for row in rows).casefold()
    assert "магазин" not in joined
    assert "яндекс" not in joined
    assert "wildberries" not in joined
