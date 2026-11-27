"""PDF → фрагменты; гибридный поиск BM25 + BGE-M3 (RRF) в пределах двигателя машины."""

from __future__ import annotations

import argparse
import json
import re
from functools import lru_cache

from urllib.parse import quote

import numpy as np

from app.config import INDEX_DIR, MANUALS_DIR, RRF_K, SKIP_EMBEDDINGS
from app.ocr_pages import ocr_manual_page, tesseract_available
from app.embeddings import encode_passages, encode_query, library_available
from app.manuals import MANUALS, Manual, manual_by_id, manuals_for

_PART_HINT = re.compile(
    r"(запчаст|детал|номенклат|артикул|обозначени[ея]\s+детал|шифр|"
    r"подшипник|сальник|прокладка|фильтр|форсунка|диск\s+сцеплен|корзина|"
    r"вилка\s+выключ|муфта\s+выключ|ремкомплект|манжет)",
    re.IGNORECASE,
)
_PROCESS_PAGE = re.compile(
    r"(?i)(техническое\s+обслуживание|порядок\s+разборк|порядок\s+сборк|"
    r"требования\s+безопасности|регулировка\s+тепловых|"
    r"перед\s+регулировкой)",
)
_TOC_DOTTED = re.compile(r"[\.…]{3,}\s*\d{1,3}\s*$")
_TOC_TRAIL_PAGE = re.compile(r"\S.{6,}\s{2,}\d{1,3}\s*$")
_TOC_TITLE = re.compile(r"(?i)^\s*(содержание|оглавление|contents)\b")


def is_contents_page(text: str) -> bool:
    """Оглавление / содержание PDF — не процедура ремонта и не инструкция по эксплуатации."""
    raw = text or ""
    if not raw.strip():
        return False
    head = re.sub(r"\s+", " ", raw[:120]).casefold()
    if "содержание" in head or "оглавление" in head or head.lstrip().startswith("contents"):
        return True
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) < 5:
        return False
    titled = sum(1 for line in lines[:8] if _TOC_TITLE.search(line))
    dotted = sum(1 for line in lines if _TOC_DOTTED.search(line) or _TOC_TRAIL_PAGE.search(line))
    if titled and dotted >= 3:
        return True
    return (dotted / len(lines)) >= 0.55

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


def _search_excerpt(text: str, limit: int = 420) -> str:
    """Фрагмент для UI/агента: целые фразы, без обрыва на середине слова."""
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return ""
    start = 0
    for index, ch in enumerate(raw):
        if ch.isupper() or ch.isdigit() or ch in "«\"'(":
            start = index
            break
        if index > 48:
            break
    raw = raw[start:].strip()
    parts = re.split(r"(?<=[.!?…])\s+", raw)
    out: list[str] = []
    total = 0
    for part in parts:
        piece = part.strip()
        if len(piece) < 8:
            continue
        if total and total + 1 + len(piece) > limit:
            break
        out.append(piece)
        total += len(piece) + (1 if total else 0)
        if total >= int(limit * 0.65):
            break
    if out:
        return " ".join(out)
    cut = raw[:limit].rsplit(" ", 1)[0].strip()
    return f"{cut}…" if cut else raw[:limit]


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


def rrf_fusion(rank_lists: list[list[int]], *, k: int = RRF_K, limit: int = 50) -> list[tuple[int, float]]:
    """Объединение ранжирований reciprocal rank fusion. Индексы — позиции в общем списке фрагментов."""
    scores: dict[int, float] = {}
    for ranks in rank_lists:
        for rank, index in enumerate(ranks[:limit]):
            scores[index] = scores.get(index, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def build_index(*, with_vectors: bool | None = None, with_ocr: bool = False) -> dict:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    pages_path = INDEX_DIR / "pages.jsonl"
    chunks_path = INDEX_DIR / "chunks.jsonl"
    empty: list[dict] = []
    page_count = 0
    chunk_count = 0
    missing: list[str] = []
    ocr_applied = 0
    chunk_records: list[dict] = []
    use_ocr = with_ocr and tesseract_available()
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
                body = text
                ocr_flag = False
                if use_ocr and len(body.strip()) < EMPTY_PAGE_CHARS:
                    extra = ocr_manual_page(manual.manual_id, number)
                    if len(extra.strip()) > len(body.strip()):
                        body = extra
                        ocr_flag = True
                        ocr_applied += 1
                record = {
                    "manual": manual.manual_id,
                    "engines": list(manual.engines),
                    "file": manual.filename,
                    "page": number,
                    "chars": len(body.strip()),
                    "text": body,
                    "ocr": ocr_flag,
                }
                pages_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                if record["chars"] < EMPTY_PAGE_CHARS:
                    empty.append(
                        {
                            "manual": manual.manual_id,
                            "page": number,
                            "chars": record["chars"],
                            "ocr_tried": use_ocr,
                        }
                    )
                    continue
                for piece in chunk_text(body):
                    chunk_count += 1
                    row = {
                        "chunk_id": chunk_count - 1,
                        "manual": manual.manual_id,
                        "engines": list(manual.engines),
                        "page": number,
                        "text": piece,
                    }
                    chunk_records.append(row)
                    chunks_file.write(json.dumps(row, ensure_ascii=False) + "\n")
    vector_report: dict = {"vectors": 0, "skipped": True}
    want_vectors = with_vectors if with_vectors is not None else not SKIP_EMBEDDINGS
    if want_vectors and chunk_records and library_available():
        vector_report = _save_embeddings(chunk_records)
    elif want_vectors and not library_available():
        vector_report = {"vectors": 0, "skipped": True, "reason": "нет sentence-transformers"}
    report = {
        "pages": page_count,
        "chunks": chunk_count,
        "empty_pages": len(empty),
        "ocr_applied": ocr_applied if use_ocr else 0,
        "ocr_enabled": use_ocr,
        "missing_files": missing,
        **vector_report,
    }
    (INDEX_DIR / "report.json").write_text(
        json.dumps({**report, "empty": empty}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    load_index.cache_clear()
    return report


def _save_embeddings(chunk_records: list[dict]) -> dict:
    texts = [row["text"] for row in chunk_records]
    vectors = encode_passages(texts)
    path = INDEX_DIR / "embeddings.npz"
    np.savez_compressed(path, vectors=vectors.astype(np.float16))
    meta = {
        "model": __import__("app.config", fromlist=["EMBEDDING_MODEL"]).EMBEDDING_MODEL,
        "chunks": len(chunk_records),
        "dim": int(vectors.shape[1]),
    }
    (INDEX_DIR / "embeddings-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"vectors": len(chunk_records), "dim": meta["dim"], "skipped": False}


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
    pages = _read_jsonl(INDEX_DIR / "pages.jsonl")
    chunks = _read_jsonl(INDEX_DIR / "chunks.jsonl")
    for index, row in enumerate(chunks):
        row.setdefault("chunk_id", index)
    return pages, chunks


class ManualSearch:
    def __init__(self) -> None:
        self.pages, self.chunks = load_index()
        self._bm25: dict[str, object] = {}
        self._by_engine: dict[str, list[dict]] = {}
        self._embedding_matrix: np.ndarray | None = None
        self._load_embeddings()

    def ready(self) -> bool:
        return bool(self.chunks)

    def hybrid_ready(self) -> bool:
        return self._embedding_matrix is not None and library_available()

    def vector_stats(self) -> dict:
        if self._embedding_matrix is None:
            return {"count": 0, "dim": 0}
        return {"count": int(self._embedding_matrix.shape[0]), "dim": int(self._embedding_matrix.shape[1])}

    def _load_embeddings(self) -> None:
        path = INDEX_DIR / "embeddings.npz"
        if not path.is_file():
            return
        try:
            data = np.load(path)
            matrix = np.asarray(data["vectors"], dtype=np.float32)
            if matrix.shape[0] != len(self.chunks):
                return
            self._embedding_matrix = matrix
        except OSError:
            return

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
        wanted = set(pages[:5])
        out: list[dict] = []
        for row in self.pages:
            if row["manual"] != found.manual_id or row["page"] not in wanted:
                continue
            text = row["text"]
            if is_contents_page(text):
                out.append(
                    {
                        "manual": row["manual"],
                        "page": row["page"],
                        "text": "",
                        "text_sparse": True,
                        "is_contents": True,
                        "error": "страница оглавления запрещена для демонстрации механику",
                        "page_image_url": None,
                    }
                )
                continue
            out.append(
                {
                    "manual": row["manual"],
                    "page": row["page"],
                    "text": text[:4000],
                    "text_sparse": len(text.strip()) < EMPTY_PAGE_CHARS,
                    "is_contents": False,
                    "page_image_url": page_image_url(found.manual_id, row["page"]),
                }
            )
        return out

    def search_spare_parts(self, engine: str, query: str, limit: int = 8) -> list[dict]:
        hits = self.search(engine, query, limit=limit * 4)
        rows: list[dict] = []
        for hit in hits:
            excerpt = hit.get("excerpt") or ""
            body = self.page_text(engine, hit["manual"], hit["page"]) or excerpt
            if is_contents_page(body) or is_contents_page(excerpt):
                continue
            # Страницы чистого ТО/процедуры без намёка на деталь — не каталог запчастей.
            if _PROCESS_PAGE.search(body) and not _PART_HINT.search(body):
                continue
            if not _PART_HINT.search(body) and not re.search(r"\d{2,5}[-.]\d{2,}", body):
                continue
            rows.append(
                {
                    "manual": hit["manual"],
                    "page": hit["page"],
                    "excerpt": excerpt,
                    "page_image_url": page_image_url(hit["manual"], hit["page"]),
                    "score": hit.get("score"),
                    "bm25": hit.get("bm25"),
                    "vector": hit.get("vector"),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def search(self, engine: str, query: str, limit: int = 5) -> list[dict]:
        rows = self._engine_chunks(engine)
        tokens = tokenize(query)
        if not rows or not tokens:
            return []
        scorer = self._engine_bm25(engine, rows)
        bm25_scores = scorer.get_scores(tokens)
        bm25_order = sorted(
            range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
        )

        rank_lists = [bm25_order]
        vector_scores: dict[int, float] = {}

        if self.hybrid_ready() and self._embedding_matrix is not None:
            ids = [int(row["chunk_id"]) for row in rows]
            sub = self._embedding_matrix[ids]
            try:
                qvec = encode_query(query)
                sims = sub @ qvec
                vec_order = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
                rank_lists.append(vec_order)
                for index, value in enumerate(sims):
                    vector_scores[index] = float(value)
            except Exception:
                pass

        if len(rank_lists) == 1:
            fused = [(index, float(bm25_scores[index])) for index in bm25_order if bm25_scores[index] > 0]
        else:
            fused = rrf_fusion(rank_lists, limit=max(limit * 8, 40))

        hits: list[dict] = []
        for index, score in fused:
            if len(hits) >= limit:
                break
            if len(rank_lists) == 1 and score <= 0:
                break
            row = rows[index]
            if is_contents_page(row.get("text") or ""):
                continue
            hits.append(
                {
                    "manual": row["manual"],
                    "page": row["page"],
                    "excerpt": _search_excerpt(row["text"]),
                    "score": round(float(score), 4),
                    "bm25": round(float(bm25_scores[index]), 3) if bm25_scores[index] > 0 else None,
                    "vector": round(vector_scores[index], 4) if index in vector_scores else None,
                }
            )
        return hits

    def _engine_chunks(self, engine: str) -> list[dict]:
        if engine not in self._by_engine:
            self._by_engine[engine] = [
                row
                for row in self.chunks
                if engine in row.get("engines", []) and not is_contents_page(row.get("text") or "")
            ]
        return self._by_engine[engine]

    def _engine_bm25(self, engine: str, rows: list[dict]):
        if engine not in self._bm25:
            from rank_bm25 import BM25Okapi

            self._bm25[engine] = BM25Okapi([tokenize(row["text"]) for row in rows])
        return self._bm25[engine]


def page_image_url(manual_id: str, page: int) -> str:
    return f"/api/page-image?manual={quote(manual_id)}&page={page}"


def render_page_png(manual_id: str, page: int, scale: float = 2.0) -> bytes | None:
    found = manual_by_id(manual_id)
    if found is None:
        return None
    path = MANUALS_DIR / found.filename
    if not path.is_file():
        return None
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(path))
    try:
        if page < 1 or page > len(document):
            return None
        pdf_page = document[page - 1]
        try:
            bitmap = pdf_page.render(scale=scale)
            try:
                pil = bitmap.to_pil()
                from io import BytesIO

                buf = BytesIO()
                pil.save(buf, format="PNG")
                return buf.getvalue()
            finally:
                bitmap.close()
        finally:
            pdf_page.close()
    finally:
        document.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка индекса руководств")
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Tesseract для страниц без текстового слоя",
    )
    parser.add_argument(
        "--skip-vectors",
        action="store_true",
        help="только BM25 (без BGE-M3)",
    )
    parser.add_argument(
        "--vectors-only",
        action="store_true",
        help="пересчитать embeddings.npz по существующему chunks.jsonl",
    )
    args = parser.parse_args()
    if args.vectors_only:
        chunks = _read_jsonl(INDEX_DIR / "chunks.jsonl")
        for index, row in enumerate(chunks):
            row.setdefault("chunk_id", index)
        report = _save_embeddings(chunks) if chunks and library_available() else {"skipped": True}
        print(json.dumps(report, ensure_ascii=False))
        return
    report = build_index(with_vectors=not args.skip_vectors, with_ocr=args.ocr)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()