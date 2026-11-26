"""Постраничный разбор PDF и лексический поиск по документам выбранного двигателя.

Векторный индекс (BGE-M3) сюда не входит: отдельный шаг, когда лексический поиск уже сверен.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from app.config import INDEX_DIR, MANUALS_DIR
from app.manuals import MANUALS, Manual, manual_by_id, manuals_for

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
EMPTY_PAGE_CHARS = 40
_TOKEN = re.compile(r"[0-9a-zа-яё][0-9a-zа-яё./-]{1,}", re.IGNORECASE)


def _stemmer():
    import snowballstemmer

    return snowballstemmer.stemmer("russian")


def tokenize(text: str) -> list[str]:
    words = [word.casefold().replace("ё", "е") for word in _TOKEN.findall(text)]
    try:
        return _stemmer().stemWords(words)
    except Exception:
        return words


def chunk_text(text: str) -> list[str]:
    compact = re.sub(r"[ \t]+\n", "\n", text).strip()
    if not compact:
        return []
    if len(compact) <= CHUNK_SIZE:
        return [compact]
    parts: list[str] = []
    start = 0
    while start < len(compact):
        end = min(len(compact), start + CHUNK_SIZE)
        if end < len(compact):
            cut = compact.rfind("\n", start + CHUNK_SIZE // 2, end)
            if cut != -1:
                end = cut
        piece = compact[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= len(compact):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return parts


def extract_pages(path) -> list[tuple[int, str]]:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(path))
    pages: list[tuple[int, str]] = []
    try:
        for index in range(len(document)):
            page = document[index]
            text_page = page.get_textpage()
            try:
                text = text_page.get_text_bounded() or ""
            finally:
                text_page.close()
                page.close()
            pages.append((index + 1, text))
    finally:
        document.close()
    return pages


def build_index() -> dict:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    pages_path = INDEX_DIR / "pages.jsonl"
    chunks_path = INDEX_DIR / "chunks.jsonl"
    empty: list[dict] = []
    page_count = 0
    chunk_count = 0
    missing: list[str] = []
    with pages_path.open("w", encoding="utf-8") as pages_file, chunks_path.open(
        "w", encoding="utf-8"
    ) as chunks_file:
        for manual in MANUALS:
            source = MANUALS_DIR / manual.filename
            if not source.is_file():
                missing.append(manual.filename)
                continue
            for number, text in extract_pages(source):
                page_count += 1
                record = {
                    "manual": manual.manual_id,
                    "engines": list(manual.engines),
                    "file": manual.filename,
                    "page": number,
                    "chars": len(text.strip()),
                    "text": text,
                }
                pages_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                if record["chars"] < EMPTY_PAGE_CHARS:
                    empty.append(
                        {"manual": manual.manual_id, "page": number, "chars": record["chars"]}
                    )
                    continue
                for piece in chunk_text(text):
                    chunk_count += 1
                    chunks_file.write(
                        json.dumps(
                            {
                                "manual": manual.manual_id,
                                "engines": list(manual.engines),
                                "page": number,
                                "text": piece,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
    report = {
        "pages": page_count,
        "chunks": chunk_count,
        "empty_pages": len(empty),
        "missing_files": missing,
    }
    (INDEX_DIR / "report.json").write_text(
        json.dumps({**report, "empty": empty}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    load_index.cache_clear()
    return report


def _read_jsonl(path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


@lru_cache(maxsize=1)
def load_index() -> tuple[list[dict], list[dict]]:
    return _read_jsonl(INDEX_DIR / "pages.jsonl"), _read_jsonl(INDEX_DIR / "chunks.jsonl")


class ManualSearch:
    def __init__(self) -> None:
        self.pages, self.chunks = load_index()
        self._bm25: dict[str, object] = {}
        self._by_engine: dict[str, list[dict]] = {}

    def ready(self) -> bool:
        return bool(self.chunks)

    def allowed(self, engine: str) -> list[Manual]:
        return manuals_for(engine)

    def page_text(self, engine: str, manual_label: str, page: int) -> str | None:
        found = manual_by_id(manual_label)
        if found is None or engine not in found.engines:
            return None
        for row in self.pages:
            if row["manual"] == found.manual_id and row["page"] == page:
                return row["text"]
        return None

    def read_pages(self, engine: str, manual_label: str, pages: list[int]) -> list[dict]:
        found = manual_by_id(manual_label)
        if found is None or engine not in found.engines:
            return []
        wanted = set(pages[:3])
        return [
            {"manual": row["manual"], "page": row["page"], "text": row["text"][:4000]}
            for row in self.pages
            if row["manual"] == found.manual_id and row["page"] in wanted
        ]

    def search(self, engine: str, query: str, limit: int = 5) -> list[dict]:
        rows = self._engine_chunks(engine)
        tokens = tokenize(query)
        if not rows or not tokens:
            return []
        scorer = self._engine_bm25(engine, rows)
        scores = scorer.get_scores(tokens)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        hits: list[dict] = []
        for index in order:
            if scores[index] <= 0 or len(hits) >= limit:
                break
            row = rows[index]
            hits.append(
                {
                    "manual": row["manual"],
                    "page": row["page"],
                    "excerpt": row["text"][:500],
                    "score": round(float(scores[index]), 3),
                }
            )
        return hits

    def _engine_chunks(self, engine: str) -> list[dict]:
        if engine not in self._by_engine:
            self._by_engine[engine] = [
                row for row in self.chunks if engine in row.get("engines", [])
            ]
        return self._by_engine[engine]

    def _engine_bm25(self, engine: str, rows: list[dict]):
        if engine not in self._bm25:
            from rank_bm25 import BM25Okapi

            self._bm25[engine] = BM25Okapi([tokenize(row["text"]) for row in rows])
        return self._bm25[engine]


def main() -> None:
    report = build_index()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
