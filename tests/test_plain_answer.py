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
