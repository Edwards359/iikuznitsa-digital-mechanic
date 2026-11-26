"""Черновики заявок и уже отправленные номера. Отправка только сохранённого состава."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from app.config import DB_PATH

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS drafts (
            id TEXT PRIMARY KEY,
            vehicle_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ticket_id TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            vehicle_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return connection


def canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def save_draft(vehicle_id: str, session_id: str, payload: dict, reason: str) -> dict:
    draft_id = uuid.uuid4().hex[:12]
    digest = payload_hash(payload)
    created = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO drafts (id, vehicle_id, session_id, payload, payload_hash, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (draft_id, vehicle_id, session_id, canonical(payload), digest, reason, created),
        )
    return {"draft_id": draft_id, "payload": payload, "reason": reason, "payload_hash": digest}


def get_draft(draft_id: str) -> dict | None:
    with _lock, _connect() as connection:
        row = connection.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    if row is None:
        return None
    return {
        "draft_id": row["id"],
        "vehicle_id": row["vehicle_id"],
        "session_id": row["session_id"],
        "payload": json.loads(row["payload"]),
        "payload_hash": row["payload_hash"],
        "reason": row["reason"],
        "ticket_id": row["ticket_id"],
    }


def mark_submitted(draft_id: str, ticket_id: str) -> None:
    draft = get_draft(draft_id)
    if draft is None:
        return
    created = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as connection:
        connection.execute(
            "UPDATE drafts SET ticket_id = ? WHERE id = ?",
            (ticket_id, draft_id),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO tickets (ticket_id, vehicle_id, session_id, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                draft["vehicle_id"],
                draft["session_id"],
                canonical(draft["payload"]),
                created,
            ),
        )


def history(vehicle_id: str, session_id: str | None = None) -> list[dict]:
    query = "SELECT ticket_id, vehicle_id, session_id, created_at FROM tickets WHERE vehicle_id = ?"
    args: list[str] = [vehicle_id]
    if session_id:
        query += " AND session_id = ?"
        args.append(session_id)
    query += " ORDER BY created_at"
    with _lock, _connect() as connection:
        rows = connection.execute(query, args).fetchall()
    return [dict(row) for row in rows]
