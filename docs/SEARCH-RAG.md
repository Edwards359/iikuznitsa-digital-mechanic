# Гибридный поиск по руководствам

<!-- markdownlint-disable MD013 -->

## Зачем два канала

| Канал | Сильная сторона | Слабая сторона |
| --- | --- | --- |
| **BM25** (лексика) | Номера деталей, моменты затяжки, редкие аббревиатуры | Синонимы и перефраз |
| **BGE-M3** (dense) | Смысловая близость, мультиязычность | Точные коды и числа без контекста |

Объединение **RRF** (Reciprocal Rank Fusion): для каждого фрагмента score = Σ 1/(k+rank_i), k=`RRF_K` (60). Так мы не подбираем веса вручную на хакатоне, но получаем устойчивый профессиональный baseline.

## Модель embeddings

- **BAAI/bge-m3** через `sentence-transformers`, запуск **на CPU** (torch CPU wheel).
- Запрос: префикс `Represent this sentence for searching relevant passages:` (рекомендация для dense retrieval).
- Пассажи: текст фрагмента как в PDF (без префикса).
- Векторы L2-нормализованы; скор = скалярное произведение.

Токены облачного LLM на индексацию **не расходуются**.

## Файлы индекса

| Файл | Содержимое |
| --- | --- |
| `pages.jsonl` | Полный текст страницы, метаданные |
| `chunks.jsonl` | Фрагменты с `chunk_id`, привязка manual/page/engine |
| `embeddings.npz` | Матрица `(n_chunks, dim)`, float16 |
| `embeddings-meta.json` | модель, dim, число фрагментов |
| `report.json` | статистика сборки, пустые страницы |

## Сборка

```text
# Полный цикл (текст + векторы), PDF в data/manuals
set HF_HOME=D:\hf-cache
python -m app.rag

# Только BM25 (быстро, без torch)
set SKIP_EMBEDDINGS=1
python -m app.rag

# OCR для «пустых» страниц (сканы без текстового слоя); нужен Tesseract
python -m app.rag --ocr

# Пересчитать векторы по готовому chunks.jsonl
python -m app.rag --vectors-only
```

В Docker-образе `web` установлены `tesseract-ocr`, `tesseract-ocr-rus`, `tesseract-ocr-eng` (`app/ocr_pages.py`, `pytesseract`). В `report.json` поля `ocr_enabled`, `ocr_applied`; в `pages.jsonl` — флаг `ocr` на странице. Язык: `OCR_LANG` (по умолчанию `rus+eng`). OCR идёт только если после извлечения PDF текст короче `EMPTY_PAGE_CHARS` (40 символов).

Переменные: `EMBEDDING_MODEL`, `EMBEDDING_BATCH_SIZE`, `INDEX_DIR`, `MANUALS_DIR`.

## Онлайн-поиск

`ManualSearch.search(engine, query)`:

1. Фильтр фрагментов по `engine` ∈ `engines[]`.
2. BM25 → упорядочивание индексов.
3. Если есть `embeddings.npz` и библиотека установлена — dense top + RRF.
4. В ответе агенту: `manual`, `page`, `excerpt`, `score`, опционально `bm25` и `vector` для отладки.

`search_spare_parts` — тот же ранжированный список, отбор строк с признаками номенклатуры.

## Деградация

- Нет PDF / индекса → `search_manual` возвращает ошибку «индекс не собран».
- Нет `embeddings.npz` → работает только BM25 (`search_hybrid: false` в `/api/health`).
- VPS: модель качается при первом `python -m app.rag` (нужен `HF_HOME` или сеть); на прод лучше собрать индекс локально и смонтировать `data/index`.

## Ограничения (честно для жюри)

- Страницы-сканы без текстового слоя в BM25/BGE почти пусты — см. `text_sparse` и PNG.
- Индекс не общий FAISS: при ~тысячах фрагментов достаточно numpy dot по срезу двигателя (десятки–сотни строк).
