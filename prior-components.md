# Ранее созданные компоненты

<!-- markdownlint-disable MD013 -->

Согласно п. 4.5 Положения: переиспользуемые части вне кода, написанного в спринте.

| Компонент | Источник | Назначение в решении |
| --- | --- | --- |
| — | — | **Собственный код агента, RAG, API и UI написан в спринте** (репозиторий `iikuznitsa-digital-mechanic`, коммиты с 26.11.2026). Отдельных коммитов `reuse:` нет. |
| Открытые библиотеки | PyPI / Hugging Face | FastAPI, uvicorn, pypdfium2, snowballstemmer, sentence-transformers (BGE-M3), numpy, pytesseract и др. — см. `requirements.txt` |
| Модель embeddings | `BAAI/bge-m3` | Локальная индексация и гибридный поиск (без токенов облачного LLM) |
| Yandex Cloud | API заказчика / партнёра | YandexGPT Pro для диалога; опционально SpeechKit при `VOICE_MODE=yandex` |
| Данные задачи | Материалы организаторов | PDF руководств и CSV машин — только на стенде, не в Git |

Инфраструктура деплоя: Docker, Caddy/sslh на VPS команды (настройка в спринте).
