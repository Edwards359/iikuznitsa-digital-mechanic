from app.agent import _tidy_excerpt


def test_tidy_excerpt_drops_midword_prefix() -> None:
    raw = (
        "ого вала. - выделение охлаждающей жидкости или смеси ее со смазкой "
        "из дренажного отверстия водяного насоса, при любых режимах работы, "
        "а также при остановке двигателя, допускается из расчёта не более "
        "одной капли в 3 мин. - выделение в период обкатки отдельных капель."
    )
    out = _tidy_excerpt(raw, limit=220)
    assert not out.lower().startswith("ого")
    assert "выделение охлаждающей" in out.casefold()
    assert len(out) <= 240


def test_tidy_excerpt_keeps_clean_start() -> None:
    raw = "Проверить тепловой зазор клапанов на холодном двигателе. Затем установить крышку."
    out = _tidy_excerpt(raw, limit=120)
    assert out.startswith("Проверить")
