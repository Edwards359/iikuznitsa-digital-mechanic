"""Распознавание речи через Yandex SpeechKit (без Google в браузере)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import httpx

from app.config import YANDEX_API_KEY, YANDEX_FOLDER_ID

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"


class SttError(RuntimeError):
    pass


def _prepare_audio(blob: bytes, mime: str) -> tuple[bytes, str]:
    lowered = (mime or "").lower()
    if "ogg" in lowered:
        return blob, "oggopus"
    if "mpeg" in lowered or "mp3" in lowered:
        return blob, "mp3"
    # Chrome чаще отдаёт webm/opus — SpeechKit ждёт oggopus, перекодируем ffmpeg.
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "chunk.webm"
        dst = Path(tmp) / "chunk.ogg"
        src.write_bytes(blob)
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(src),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "libopus",
                str(dst),
            ],
            capture_output=True,
            timeout=25,
            check=False,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")[:240]
            raise SttError(f"не удалось перевести webm в ogg: {err}")
        return dst.read_bytes(), "oggopus"


def recognize(blob: bytes, mime: str = "") -> str:
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        raise SttError("Yandex SpeechKit не настроен")
    if len(blob) < 80:
        return ""
    payload, fmt = _prepare_audio(blob, mime)
    params = {
        "folderId": YANDEX_FOLDER_ID,
        "lang": "ru-RU",
        "format": fmt,
        "topic": "general",
    }
    response = httpx.post(
        STT_URL,
        params=params,
        content=payload,
        headers={"Authorization": f"Api-Key {YANDEX_API_KEY}"},
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise SttError(f"SpeechKit {response.status_code}: {response.text[:200]}")
    body = response.json()
    return str(body.get("result") or "").strip()