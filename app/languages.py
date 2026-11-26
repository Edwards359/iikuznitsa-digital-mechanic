"""Коды языка ответа (СНГ + хинди). Одна LLM, без отдельных языковых API."""

from __future__ import annotations

# Код BCP-47 → как просим модель формулировать ответ
ANSWER_LANGUAGES: dict[str, str] = {
    "ru": "русском",
    "uk": "украинском",
    "be": "белорусском",
    "kk": "казахском",
    "uz": "узбекском",
    "ky": "киргизском",
    "tg": "таджикском",
    "hy": "армянском",
    "az": "азербайджанском",
    "ka": "грузинском",
    "ro": "румынском",
    "hi": "хинди",
}


def answer_lang_prefix(code: str | None) -> str:
    if not code or code == "ru":
        return ""
    label = ANSWER_LANGUAGES.get(code)
    if label is None:
        return ""
    return (
        f"Ответ механику на {label} языке. Названия документов, номера страниц и обозначения деталей "
        f"оставь как в руководстве.\n"
    )