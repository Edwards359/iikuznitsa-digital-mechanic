"""OCR для страниц PDF без текстового слоя (Tesseract, офлайн)."""

from __future__ import annotations

import shutil
from io import BytesIO

from app.config import OCR_LANG


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_page_png(png: bytes, *, lang: str | None = None) -> str:
    if not tesseract_available():
        return ""
    import pytesseract
    from PIL import Image

    image = Image.open(BytesIO(png))
    chosen = lang or OCR_LANG
    try:
        return (pytesseract.image_to_string(image, lang=chosen) or "").strip()
    except pytesseract.TesseractError:
        return ""


def ocr_manual_page(manual_id: str, page: int, *, scale: float = 2.0) -> str:
    from app.rag import render_page_png

    blob = render_page_png(manual_id, page, scale=scale)
    if not blob:
        return ""
    return ocr_page_png(blob)