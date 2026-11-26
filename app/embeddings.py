"""Локальные embeddings BGE-M3 для гибридного поиска. Токены API не тратятся."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from app.config import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_ST_AVAILABLE: bool | None = None


def library_available() -> bool:
    global _ST_AVAILABLE
    if _ST_AVAILABLE is not None:
        return _ST_AVAILABLE
    try:
        import sentence_transformers  # noqa: F401

        _ST_AVAILABLE = True
    except ImportError:
        _ST_AVAILABLE = False
    return _ST_AVAILABLE


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    if not library_available():
        raise RuntimeError("sentence-transformers не установлен")
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def encode_passages(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = _model()
    vectors = model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 64,
        convert_to_numpy=True,
    )
    return np.asarray(vectors, dtype=np.float32)


def encode_query(query: str) -> np.ndarray:
    model = _model()
    prompt = QUERY_PREFIX + (query or "").strip()
    vector = model.encode(
        [prompt],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return np.asarray(vector[0], dtype=np.float32)