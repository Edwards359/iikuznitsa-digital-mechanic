"""OCR опционален в CI; в Docker-образе web — обязателен."""

from app.ocr_pages import ocr_page_png, tesseract_available


def test_tesseract_optional_import() -> None:
    _ = tesseract_available()


def test_ocr_empty_png() -> None:
    if not tesseract_available():
        return
    # 1×1 белый PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00"
        b"\x05\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    text = ocr_page_png(png)
    assert isinstance(text, str)