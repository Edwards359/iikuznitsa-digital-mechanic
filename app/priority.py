"""Приоритет заявки считается кодом. Модель может только сообщить запрет эксплуатации."""

from __future__ import annotations

from app.config import HIGH_SCORE, LOW_CONFIDENCE, WEAK_SCORE


def choose_urgency(
    sessions: list[dict],
    current: dict,
    *,
    forbids_operation: bool = False,
) -> tuple[str, str]:
    confidence = current.get("confidence")
    score = current.get("anomaly_score")
    quality = current.get("signal_quality")
    if quality == "warning" or (confidence is not None and confidence < LOW_CONFIDENCE):
        return "low", "Низкий: помехи или уверенность ниже 0,56, приоритет не повышается"
    if forbids_operation:
        return "high", "Высокий: в руководстве этого узла нельзя продолжать эксплуатацию"
    same_scores = [
        item["anomaly_score"]
        for item in sessions
        if item.get("status") == "anomaly"
        and item.get("anomaly_type") == current.get("anomaly_type")
        and item.get("anomaly_score") is not None
    ]
    if len(same_scores) >= 3 and same_scores[-3] < same_scores[-2] < same_scores[-1]:
        shown = " → ".join(f"{value:.2f}" for value in same_scores[-3:])
        return "high", f"Высокий: оценка того же признака растёт {shown}"
    if (
        score is not None
        and score >= HIGH_SCORE
        and confidence is not None
        and confidence >= 0.7
    ):
        return "high", "Высокий: оценка не ниже 0,90 при уверенности не ниже 0,70"
    if len(same_scores) <= 1 and score is not None and score < WEAK_SCORE:
        return "low", "Низкий: признак впервые и оценка слабая"
    return "medium", "Средний: отклонение без усиления по последним проверкам"
