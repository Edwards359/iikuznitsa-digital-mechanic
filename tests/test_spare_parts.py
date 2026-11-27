from app.agent import (
    _spare_label,
    extract_part_name,
    fault_spare_query,
    is_part_label,
)
from app.web_parts import internet_spare_candidates


def test_fault_spare_query_uses_code_and_title() -> None:
    q = fault_spare_query(
        {
            "anomaly_type": "F06",
            "anomaly_title": "Шум в зоне сцепления",
            "description": "шум меняется при нажатии педали",
        }
    )
    assert "F06" in q
    assert "сцепления" in q.casefold()


def test_fault_spare_query_drops_process_extra() -> None:
    q = fault_spare_query(
        {"anomaly_type": "F08", "anomaly_title": "Дизельная топливоподача"},
        extra="Проверить тепловой зазор клапанов на холодном двигателе",
    )
    assert "Проверить" not in q
    assert "F08" in q
    assert "топливоподача" in q.casefold()


def test_spare_label_is_part_not_process() -> None:
    label = _spare_label(
        {
            "excerpt": "Выжимной подшипник сцепления. Заменить при износе.",
            "manual": "236.01.01 РК",
            "page": 42,
        }
    )
    assert label == "Выжимной подшипник сцепления"
    assert is_part_label(label)


def test_spare_label_rejects_maintenance_process() -> None:
    label = _spare_label(
        {
            "excerpt": (
                "63 ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ ФРИКЦИОННОГО СЦЕПЛЕНИЯ "
                "В эксплуатации периодически проводить регулировку свободного хода."
            ),
            "manual": "236-3902150-Б РЭ",
            "page": 63,
        }
    )
    assert label == ""


def test_is_part_label_rejects_verbs() -> None:
    assert not is_part_label("Проверить натяжение ремня")
    assert not is_part_label("Отрегулировать зазор клапанов")
    assert not is_part_label("Техническое обслуживание сцепления")
    assert not is_part_label("форсунки Подтянуть гайку крепления стакана")
    assert not is_part_label("местах манжетных уплотнений без")
    assert not is_part_label("пружины и др")
    assert not is_part_label("Толкатель")
    assert not is_part_label("Внутренними пружинами")
    assert not is_part_label("Количество Примечания Прокладка (поз")
    assert is_part_label("Подшипник выжимной сцепления")
    assert is_part_label("Регулировочная шайба зазора клапанов")
    assert is_part_label("Форсунка топливная")
    assert is_part_label("Крепёж узла (болты/гайки, комплект)")


def test_extract_part_name_from_mixed_excerpt() -> None:
    name = extract_part_name(
        "При износе заменить подшипник выжимной сцепления и вилку выключения."
    )
    assert name is not None
    assert "подшипник" in name.casefold()


def test_f08_internet_candidates_are_fuel_parts() -> None:
    rows = internet_spare_candidates("F08", anomaly_type="F08", anomaly_title="Дизельная топливоподача")
    joined = " ".join(row["label"] for row in rows).casefold()
    assert "форсунка" in joined or "топлив" in joined
    assert "техническое обслуживание" not in joined
    assert all(is_part_label(row["label"]) for row in rows)
