# Архитектура «Цифровой механик» (репозиторий сдачи)

<!-- markdownlint-disable MD013 -->

Документ для жюри и сопровождения: как устроены компоненты и потоки данных на стенде спринта.

## Компоненты

```text
механик → HTTPS (sslh/Caddy) → FastAPI (app.main)
                │
                ├─ static/ — веб-чат, пошаговый ремонт, карточка машины
                ├─ Consultant (app.agent) — цикл LLM + инструменты, max MAX_STEPS
                ├─ ManualSearch (app.rag) — гибрид BM25 + BGE-M3
                ├─ SQLite (app.store) — черновики, заявки, консультации
                ├─ journal.jsonl — метаданные шагов и токенов
                ├─ mock-ml:8001 — результат акустической проверки
                └─ mock-toir:8002 — приём заявок TKT-…
```

## Данные

| Источник | Назначение |
| --- | --- |
| `vendor/mock/data/vehicles.json` | 50 машин, 3–5 проверок, поля без телеметрии |
| `vendor/mock/data/fault_types.json` | F01…F14 |
| `data/manuals/*.pdf` | шесть руководств (не в Git) |
| `data/index/` | `pages.jsonl`, `chunks.jsonl`, `embeddings.npz`, `report.json` |
| `app/manuals.py` | таблица «двигатель → документы» (не угадывается моделью) |

## Поиск по руководствам

1. Офлайн: `python -m app.rag` — постраничный текст, фрагменты ~900 символов, overlap 150.
2. Лексический индекс: BM25Okapi, токены со стеммером snowball (русский).
3. Векторный индекс: **BAAI/bge-m3** локально (`sentence-transformers`), нормализованные embeddings, файл `embeddings.npz` (float16).
4. Онлайн-запрос: ранжирование BM25 и косинусная близость; слияние **RRF** (`RRF_K`, по умолчанию 60). Поиск всегда в пределах фрагментов **двигателя выбранной машины**.
5. Страницы без текста: `read_pages` отдаёт `text_sparse` и `page_image_url` (PNG из PDF).

Подробнее: [SEARCH-RAG.md](SEARCH-RAG.md).

## LLM и безопасность заявки

- Поставщик на стенде: YandexGPT (`LLM_PROVIDER=yandex`). Адаптер в `app/llm.py` (тот же цикл, что и для Anthropic).
- `submit_ticket` **нет** в списке инструментов; отправка — `POST /api/drafts/{id}/confirm` после фиксации payload и хеша в SQLite.
- `draft_ticket` проверяет: страница из руководства этого двигателя, цитата есть на странице, непустые работы.

## Логирование

- Каждый consult → SQLite `consultations` + строка в `journal.jsonl`.
- Карточка машины: `GET /api/vehicles/{id}` — проверки, консультации, заявки, сумма токенов.

Логика агента по шагам: [AGENT-LOGIC.md](AGENT-LOGIC.md).
