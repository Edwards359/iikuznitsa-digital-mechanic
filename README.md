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

Пока индекс лексический (BM25 по страницам). Векторный поиск — следующий шаг, после сверки страниц.

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
