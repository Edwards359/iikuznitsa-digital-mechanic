from app.agent import plain_mechanic_text


def test_plain_mechanic_text_strips_markdown_and_tools() -> None:
    raw = """### Наблюдаемые признаки
- стук
**Вероятные причины**
search_spare_parts query="коробка F07"
#### Ремонт по шагам
1. Проверка
```json
{"a":1}
```
"""
    out = plain_mechanic_text(raw)
    assert "###" not in out
    assert "**" not in out
    assert "search_spare_parts" not in out
    assert "```" not in out
    assert "Наблюдаемые признаки" in out
    assert "Проверка" in out


def test_plain_mechanic_text_strips_tool_call_leaks() -> None:
    raw = (
        "Ремонт по шагам\n"
        "[TOOL_CALL_START]read_pages {\"manual\": \"536.01.01 РК\", \"pages\": [15]}\n"
        "1. Проверить давление топлива (236-3902150-Б РЭ, стр. 54)."
    )
    out = plain_mechanic_text(raw)
    assert "TOOL_CALL" not in out
    assert "536.01.01" not in out
    assert "Проверить давление" in out
    assert "стр. 54" in out
