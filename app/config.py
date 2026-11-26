"""Пути и лимиты. Секреты только из окружения."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _path(name: str, default: str) -> Path:
    raw = os.environ.get(name, default)
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


MOCK_ML_URL = os.environ.get("MOCK_ML_URL", "http://127.0.0.1:8001").rstrip("/")
MOCK_TOIR_URL = os.environ.get("MOCK_TOIR_URL", "http://127.0.0.1:8002").rstrip("/")
CATALOG_PATH = _path("CATALOG_PATH", "vendor/mock/data/vehicles.json")
FAULTS_PATH = _path("FAULTS_PATH", "vendor/mock/data/fault_types.json")
MANUALS_DIR = _path("MANUALS_DIR", "data/manuals")
INDEX_DIR = _path("INDEX_DIR", "data/index")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3").strip()
EMBEDDING_BATCH_SIZE = _int("EMBEDDING_BATCH_SIZE", 32)
# При сборке индекса: 1 — не считать векторы (только BM25).
SKIP_EMBEDDINGS = os.environ.get("SKIP_EMBEDDINGS", "").strip().lower() in ("1", "true", "yes")
OCR_LANG = os.environ.get("OCR_LANG", "rus+eng").strip()
# RRF (reciprocal rank fusion): k для 1/(k+rank).
RRF_K = _int("RRF_K", 60)
DB_PATH = _path("DB_PATH", "data/app.db")
JOURNAL_PATH = _path("JOURNAL_PATH", "data/journal.jsonl")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
# Дешёвая ступень, пока гоняем обвязку. На качество — claude-sonnet-5-5.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5").strip()
YANDEX_API_KEY = os.environ.get("YANDEX_API_KEY", "").strip()
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "").strip()
# Например yandexgpt/latest или yandexgpt-32k/rc
YANDEX_MODEL = os.environ.get("YANDEX_MODEL", "yandexgpt/latest").strip()
YANDEX_MODEL_URI = (
    os.environ.get("YANDEX_MODEL_URI", "").strip()
    or (f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_MODEL}" if YANDEX_FOLDER_ID else "")
)
MAX_STEPS = _int("MAX_STEPS", 8)
MAX_OUTPUT_TOKENS = _int("MAX_OUTPUT_TOKENS", 1024)

# USD за 1M токенов, вход / выход. Кэш в эту оценку не входит.
PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    # Оценка в USD, ориентир YandexGPT (сверить по биллингу консоли).
    "yandexgpt/latest": (0.40, 0.40),
    "yandexgpt/rc": (0.40, 0.40),
    "yandexgpt-32k/rc": (0.80, 0.80),
}

# Уверенность ниже этого порога не повышает приоритет (пожелание заказчика).
# Смешанная ставка по биллингу YandexGPT Pro 5 (AI Studio, 2026-11-26): ≈1,20 ₽ за 1k токенов.
YANDEX_RUB_PER_KTOK = float(os.environ.get("YANDEX_RUB_PER_KTOK", "1.20"))

# Голос по шагам ремонта: browser (бесплатно, Web Speech в браузере) | yandex (SpeechKit, платно) | off.
VOICE_STT_ENABLED = os.environ.get("VOICE_STT_ENABLED", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
_mode_env = os.environ.get("VOICE_MODE", "").strip().lower()
if _mode_env in ("off", "none", "disabled"):
    VOICE_MODE = "off"
elif _mode_env == "yandex" or (not _mode_env and VOICE_STT_ENABLED):
    VOICE_MODE = "yandex"
else:
    VOICE_MODE = "browser"

LOW_CONFIDENCE = 0.56
# По распределению anomaly_score в vehicles.json (2026-11-26): min 0.56, медиана 0.77, p90 0.90.
HIGH_SCORE = 0.90
WEAK_SCORE = 0.65
