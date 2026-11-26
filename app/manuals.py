"""Соответствие двигателя и документов. Берётся из README заглушки, не угадывается моделью."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Manual:
    manual_id: str
    filename: str
    engines: tuple[str, ...]


MANUALS: tuple[Manual, ...] = (
    Manual("236-3902150-Б РЭ", "ЯМЗ_236_руководство по эксплуатации.pdf", ("ЯМЗ-236М2",)),
    Manual("236.01.01 РК", "ЯМЗ_236_руководство по РЕМОНТУ.pdf", ("ЯМЗ-236М2",)),
    Manual("536.3902150 РЭ", "yamz-536_re_2016.pdf", ("ЯМЗ-536",)),
    Manual("536.01.02 РК", "yamz-536_rk_2013.pdf", ("ЯМЗ-536",)),
    Manual(
        "Двигатели ЗМЗ-5234.10 со сцеплением. Руководство по ремонту",
        "zmz-5234_rk_2025.pdf",
        ("ЗМЗ-5234.10",),
    ),
    Manual(
        "Руководство по эксплуатации, техническому обслуживанию и ремонту двигателей ЗМЗ-40904.10 и ЗМЗ-40905.10",
        "zmz-40904-40905_rk_2025.pdf",
        ("ЗМЗ-40905.10", "ЗМЗ-40904.10"),
    ),
)


def manuals_for(engine: str) -> list[Manual]:
    return [item for item in MANUALS if engine in item.engines]


def manual_by_id(manual_id: str) -> Manual | None:
    key = manual_id.strip().casefold()
    for item in MANUALS:
        if item.manual_id.casefold() == key:
            return item
    for item in MANUALS:
        if key in item.manual_id.casefold() or item.manual_id.casefold() in key:
            return item
    return None
