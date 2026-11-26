"""Карточки машин, проверки и справочник кодов из JSON заказчика."""

from __future__ import annotations

import json
from functools import lru_cache

from app.config import CATALOG_PATH, FAULTS_PATH

DEMO_LIMIT = 8


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_faults() -> dict[str, str]:
    with FAULTS_PATH.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    return {row["code"]: row["title"] for row in rows}


def vehicles() -> list[dict]:
    return load_catalog()["vehicles"]


def get_vehicle(vehicle_id: str) -> dict | None:
    for vehicle in vehicles():
        if vehicle["vehicle_id"] == vehicle_id:
            return vehicle
    return None


def public_vehicle(vehicle: dict) -> dict:
    return {
        "vehicle_id": vehicle["vehicle_id"],
        "garage_no": vehicle.get("garage_no"),
        "make": vehicle.get("make"),
        "model": vehicle.get("model"),
        "vehicle_type": vehicle.get("vehicle_type"),
        "engine_model": vehicle.get("engine_model"),
        "fuel": vehicle.get("fuel"),
        "sessions": [
            {
                "session_id": session["session_id"],
                "checked_at": session.get("checked_at"),
                "status": session.get("status"),
                "anomaly_type": session.get("anomaly_type"),
                "anomaly_title": session.get("anomaly_title"),
                "signal_quality": session.get("signal_quality"),
            }
            for session in vehicle.get("sessions", [])
        ],
    }


def demo_sessions() -> list[dict]:
    """Короткий набор для интерфейса: по одному отклонению на двигатель, сбой, помехи."""
    picked: list[dict] = []
    seen_engines: set[str] = set()
    failed: dict | None = None
    warning: dict | None = None
    for vehicle in vehicles():
        engine = vehicle.get("engine_model") or ""
        for session in reversed(vehicle.get("sessions", [])):
            row = _demo_row(vehicle, session)
            if failed is None and session.get("status") == "check_failed":
                failed = row
            if warning is None and session.get("signal_quality") == "warning":
                warning = row
            if (
                engine not in seen_engines
                and session.get("status") == "anomaly"
                and session.get("signal_quality") == "good"
                and (session.get("confidence") or 0) >= 0.56
            ):
                seen_engines.add(engine)
                picked.append({**row, "label": f"Отклонение, {engine}"})
    if failed is not None:
        picked.append({**failed, "label": "Сбой записи"})
    if warning is not None:
        picked.append({**warning, "label": "Помехи или низкая уверенность"})
    return picked[:DEMO_LIMIT]


def _demo_row(vehicle: dict, session: dict) -> dict:
    return {
        "vehicle_id": vehicle["vehicle_id"],
        "garage_no": vehicle.get("garage_no"),
        "engine_model": vehicle.get("engine_model"),
        "session_id": session["session_id"],
        "checked_at": session.get("checked_at"),
        "status": session.get("status"),
        "anomaly_type": session.get("anomaly_type"),
        "signal_quality": session.get("signal_quality"),
    }
