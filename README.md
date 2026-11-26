# Цифровой механик

Веб-помощник механика: результат акустической проверки, поиск по руководству двигателя этой машины, черновик заявки в ТОиР. Заявку отправляет только человек.

## Что поднять

Три процесса: заглушка ML (`8001`), заглушка ТОиР (`8002`), это приложение (`8080`). Заглушки заказчика лежат в `vendor/mock`.

```text
copy .env.example .env
```

В `.env` задать поставщика модели. С российского VPS **Anthropic и OpenAI недоступны** (403 по IP); для стенда — `LLM_PROVIDER=yandex`, ключ `YANDEX_API_KEY` и `YANDEX_FOLDER_ID` из консоли Yandex Cloud, модель `YANDEX_MODEL=yandexgpt/latest`. Локально можно `LLM_PROVIDER=anthropic` и `ANTHROPIC_API_KEY` (для демо — `claude-sonnet-5-5`).

Шесть PDF положить в `data/manuals` под именами из `app/manuals.py` (или задать `MANUALS_DIR` на папку, где они уже лежат). В Git руководства не входят.

Индекс:

```text
python -m app.rag
```

Индекс: **гибрид BM25 + BGE-M3** (RRF), см. [docs/SEARCH-RAG.md](docs/SEARCH-RAG.md). Для превью рисунков — те же PDF (`/api/page-image`).

```text
set HF_HOME=D:\hf-cache
python -m app.rag
```

Без torch на быстрый прогон: `SKIP_EMBEDDINGS=1` или `python -m app.rag --skip-vectors` (только BM25).

Агент ведёт ремонт по шагам из РК: `search_manual` → `read_pages` (до 5 стр.) → `search_spare_parts` → черновик заявки. В интерфейсе — миниатюры страниц PDF. Запчасти только из текста руководств (каталога цен нет по ТЗ).

Языки ответа: русский и ещё 11 языков СНГ + хинди (одна модель, инструкция в запросе).

Пошаговый ремонт: клавиши **← →** и кнопки в блоке «Пошаговый ремонт». Платный SpeechKit **выключен** по умолчанию (`VOICE_STT_ENABLED`); экономика и альтернативы — `docs/VOICE-ROADMAP.md`, `docs/cost-operation.md`.

Логирование: `data/journal.jsonl` (шаги агента), SQLite `consultations` и `tickets` — карточка машины в интерфейсе и `GET /api/vehicles/{id}`. Сводка токенов: `GET /api/usage/summary`. Цифры для жюри — `docs/cost-operation.md`.

Публичный стенд: `https://<IP>:8080` (sslh + Caddy, самоподписанный сертификат). HTTP на 8080 перенаправляется на HTTPS.

Логика агента и архитектура: [docs/AGENT-LOGIC.md](docs/AGENT-LOGIC.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**В перспективе:** OCR для страниц-картинок без текстового слоя.

## Локально

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m app.rag
.venv\Scripts\python -m uvicorn mock_ml.app:app --app-dir vendor/mock --port 8001
.venv\Scripts\python -m uvicorn mock_toir.app:app --app-dir vendor/mock --port 8002
.venv\Scripts\python -m uvicorn app.main:app --port 8080
```

Интерфейс: `http://127.0.0.1:8080`. В списке — демо-проверки из `vendor/mock/data/vehicles.json`.

## Docker

```text
docker compose up --build
```

Приложение: порт `8080`. Каталог `./data` смонтирован в контейнер (руководства, индекс, база заявок). В `.env` для compose адреса заглушек можно не менять: compose подставляет `http://mock-ml:8001` и `http://mock-toir:8002`.

## Проверки

```text
pytest -q
pytest -q vendor/mock/tests
```
