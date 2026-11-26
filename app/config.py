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
DB_PATH = _path("DB_PATH", "data/app.db")
JOURNAL_PATH = _path("JOURNAL_PATH", "data/journal.jsonl")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
# Дешёвая ступень, пока гоняем обвязку. На качество — claude-sonnet-5-5.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5").strip()
MAX_STEPS = _int("MAX_STEPS", 8)
MAX_OUTPUT_TOKENS = _int("MAX_OUTPUT_TOKENS", 1024)

# USD за 1M токенов, вход / выход. Кэш в эту оценку не входит.
PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}

# Уверенность ниже этого порога не повышает приоритет (пожелание заказчика).
LOW_CONFIDENCE = 0.56
# По распределению anomaly_score в vehicles.json (2026-11-26): min 0.56, медиана 0.77, p90 0.90.
HIGH_SCORE = 0.90
WEAK_SCORE = 0.65
