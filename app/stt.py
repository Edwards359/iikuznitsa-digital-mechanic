"""Распознавание речи через Yandex SpeechKit (без Google в браузере)."""

from __future__ import annotations

import httpx

from app.config import YANDEX_API_KEY, YANDEX_FOLDER_ID

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"


class SttError(RuntimeError):
    pass


def _format_for_mime(mime: str) -> str:
    lowered = (mime or "").lower()
    if "ogg" in lowered:
        return "oggopus"
    if "mpeg" in lowered or "mp3" in lowered:
        return "mp3"
    if "webm" in lowered:
        return "oggopus"
    return "oggopus"


def recognize(blob: bytes, mime: str = "") -> str:
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        raise SttError("Yandex SpeechKit не настроен")
    if len(blob) < 80:
        return ""
    fmt = _format_for_mime(mime)
    params = {
        "folderId": YANDEX_FOLDER_ID,
        "lang": "ru-RU",
        "format": fmt,
        "topic": "general",
    }
    response = httpx.post(
        STT_URL,
        params=params,
        content=blob,
        headers={"Authorization": f"Api-Key {YANDEX_API_KEY}"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise SttError(f"SpeechKit {response.status_code}: {response.text[:200]}")
    body = response.json()
    text = str(body.get("result") or "").strip()
    return text