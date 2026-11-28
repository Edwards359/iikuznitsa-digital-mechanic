"""Черновики заявок и уже отправленные номера. Отправка только сохранённого состава."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from app import config

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    path = config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
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
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS consultations (
            id TEXT PRIMARY KEY,
            vehicle_id TEXT NOT NULL,
            session_id TEXT,
            created_at TEXT NOT NULL,
            model TEXT NOT NULL,
            provider TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0,
            cost_rub REAL,
            tools_json TEXT NOT NULL,
            answer_preview TEXT NOT NULL,
            has_draft INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            repair_steps INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_consultations_vehicle ON consultations(vehicle_id, created_at)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS repair_progress (
            vehicle_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            consult_id TEXT,
            step_index INTEGER NOT NULL DEFAULT 0,
            step_total INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'in_progress',
            summary TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (vehicle_id, session_id)
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


def update_draft_payload(draft_id: str, payload: dict) -> bool:
    digest = payload_hash(payload)
    with _lock, _connect() as connection:
        row = connection.execute("SELECT id FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            return False
        connection.execute(
            "UPDATE drafts SET payload = ?, payload_hash = ? WHERE id = ?",
            (canonical(payload), digest, draft_id),
        )
    return True


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


def get_ticket(ticket_id: str) -> dict | None:
    with _lock, _connect() as connection:
        row = connection.execute(
            "SELECT ticket_id, vehicle_id, session_id, payload, created_at FROM tickets WHERE ticket_id = ?",
            (ticket_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "ticket_id": row["ticket_id"],
        "vehicle_id": row["vehicle_id"],
        "session_id": row["session_id"],
        "created_at": row["created_at"],
        "payload": json.loads(row["payload"]),
    }


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


def save_consultation(
    vehicle_id: str,
    session_id: str | None,
    *,
    model: str,
    provider: str,
    usage: dict,
    steps: list[dict],
    answer: str = "",
    error: str | None = None,
    has_draft: bool = False,
    repair_steps: int = 0,
    cost_rub: float | None = None,
) -> dict:
    consult_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat()
    tools = [step.get("tool") for step in steps if step.get("tool")]
    preview = (answer or error or "").strip().replace("\n", " ")[:480]
    inp = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    cost_usd = float(usage.get("cost_usd") or 0.0)
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO consultations (
                id, vehicle_id, session_id, created_at, model, provider,
                input_tokens, output_tokens, cost_usd, cost_rub, tools_json,
                answer_preview, has_draft, error, repair_steps
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                consult_id,
                vehicle_id,
                session_id,
                created,
                model,
                provider,
                inp,
                out,
                cost_usd,
                cost_rub,
                json.dumps(tools, ensure_ascii=False),
                preview,
                1 if has_draft else 0,
                error,
                repair_steps,
            ),
        )
    return {
        "id": consult_id,
        "vehicle_id": vehicle_id,
        "session_id": session_id,
        "created_at": created,
        "tools": tools,
    }


def consultations(
    vehicle_id: str,
    *,
    limit: int = 50,
) -> list[dict]:
    with _lock, _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, vehicle_id, session_id, created_at, model, provider,
                   input_tokens, output_tokens, cost_usd, cost_rub, tools_json,
                   answer_preview, has_draft, error, repair_steps
            FROM consultations
            WHERE vehicle_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (vehicle_id, limit),
        ).fetchall()
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["tools"] = json.loads(item.pop("tools_json") or "[]")
        item["has_draft"] = bool(item["has_draft"])
        out.append(item)
    return out


def save_repair_progress(
    vehicle_id: str,
    session_id: str,
    *,
    consult_id: str | None = None,
    step_index: int = 0,
    step_total: int = 0,
    status: str = "in_progress",
    summary: str = "",
) -> dict:
    updated = datetime.now(timezone.utc).isoformat()
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO repair_progress (
                vehicle_id, session_id, consult_id, step_index, step_total, status, summary, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vehicle_id, session_id) DO UPDATE SET
                consult_id = excluded.consult_id,
                step_index = excluded.step_index,
                step_total = excluded.step_total,
                status = excluded.status,
                summary = excluded.summary,
                updated_at = excluded.updated_at
            """,
            (
                vehicle_id,
                session_id,
                consult_id,
                step_index,
                step_total,
                status,
                summary[:800],
                updated,
            ),
        )
    return {
        "vehicle_id": vehicle_id,
        "session_id": session_id,
        "step_index": step_index,
        "step_total": step_total,
        "status": status,
        "summary": summary[:800],
        "updated_at": updated,
    }


def repair_progress(vehicle_id: str, session_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM repair_progress WHERE vehicle_id = ?"
    args: list[str] = [vehicle_id]
    if session_id:
        query += " AND session_id = ?"
        args.append(session_id)
    query += " ORDER BY updated_at DESC"
    with _lock, _connect() as connection:
        rows = connection.execute(query, args).fetchall()
    return [dict(row) for row in rows]


def usage_totals(vehicle_id: str | None = None) -> dict:
    where = ""
    args: list[str | int] = []
    if vehicle_id:
        where = " WHERE vehicle_id = ?"
        args.append(vehicle_id)
    query = f"""
        SELECT
            COUNT(*) AS consults,
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens,
            COALESCE(SUM(cost_usd), 0) AS cost_usd,
            COALESCE(SUM(cost_rub), 0) AS cost_rub
        FROM consultations{where}
    """
    with _lock, _connect() as connection:
        row = connection.execute(query, args).fetchone()
    return dict(row) if row else {}
