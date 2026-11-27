"""Smoke по 3 сценариям демо + health. Отчёт в reports/ (в Git не класть).

Примеры:
  .venv\\Scripts\\python scripts\\eval_smoke.py
  .venv\\Scripts\\python scripts\\eval_smoke.py --base-url https://5.129.222.124:8080 --llm
  .venv\\Scripts\\python scripts\\eval_smoke.py --only S3-recording-fail,S5-health
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval" / "cases" / "smoke.json"
REPORTS = ROOT / "reports"


def _request(base: str, method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
    url = base.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return {"error": f"HTTP {exc.code}", "detail": detail}


def _tools(steps: list) -> list[str]:
    return [str(s.get("tool")) for s in steps if s.get("tool")]


def _check_case(case: dict, payload: dict) -> list[str]:
    fails: list[str] = []
    expect = case.get("expect") or {}
    answer = str(payload.get("answer") or "")
    draft = payload.get("draft")
    steps = payload.get("steps") or []
    tools = _tools(steps)

    if expect.get("draft_not_null") is True and not draft:
        fails.append("ожидался draft, получен null")
    if expect.get("draft_not_null") is False and draft:
        fails.append("draft должен быть null")

    for name in expect.get("must_have_tools") or []:
        if name not in tools:
            fails.append(f"нет инструмента {name}")

    for needle in expect.get("must_mention") or []:
        if needle.casefold() not in answer.casefold():
            fails.append(f"в ответе нет «{needle}»")

    for banned in expect.get("must_not") or []:
        # «не создаём» содержит «дефектовку…» — проверяем только явные запреты без отрицания
        if banned.casefold() in answer.casefold() and "не созда" not in answer.casefold():
            fails.append(f"в ответе запрещённое «{banned}»")

    if expect.get("answer_has_page_ref") and "стр" not in answer.casefold():
        fails.append("нет ссылки на страницу (стр.)")

    min_steps = expect.get("repair_steps_min")
    if min_steps is not None and len(payload.get("repair_steps") or []) < int(min_steps):
        fails.append(f"repair_steps < {min_steps}")

    if expect.get("model") == "rules":
        usage = payload.get("usage") or {}
        if (usage.get("input_tokens") or 0) > 0:
            fails.append("ожидался rules-path без токенов LLM")

    if expect.get("ticket") == "not_submitted" and draft and draft.get("ticket_id"):
        fails.append("заявка уже отправлена (ticket_id)")

    return fails


def _run_health(base: str, case: dict) -> dict:
    health = _request(base, "GET", "/api/health", timeout=int(case.get("timeout_sec") or 15))
    expect = case.get("expect") or {}
    fails: list[str] = []
    if health.get("status") != "ok":
        fails.append(f"health.status={health.get('status')}")
    if int(health.get("index_chunks") or 0) < int(expect.get("min_chunks") or 0):
        fails.append("мало chunks")
    if expect.get("search_hybrid") and not health.get("search_hybrid"):
        fails.append("search_hybrid=false")
    if int(health.get("vehicles") or 0) != int(expect.get("vehicles") or 50):
        fails.append("vehicles != 50")
    return {
        "id": case["id"],
        "ok": not fails,
        "fails": fails,
        "skipped": False,
        "health": {
            "provider": health.get("provider"),
            "chunks": health.get("index_chunks"),
            "hybrid": health.get("search_hybrid"),
        },
    }


def _run_confirm_gate(case: dict) -> dict:
    agent = (ROOT / "app" / "agent.py").read_text(encoding="utf-8")
    fails: list[str] = []
    if '"name": "submit_ticket"' in agent or "name': 'submit_ticket'" in agent:
        fails.append("в TOOLS появился submit_ticket")
    if "confirm_draft" not in agent:
        fails.append("нет confirm_draft")
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    if "/drafts/{draft_id}/confirm" not in main:
        fails.append("нет маршрута confirm")
    return {"id": case["id"], "ok": not fails, "fails": fails, "skipped": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval smoke «Цифровой механик»")
    parser.add_argument(
        "--base-url",
        default="https://5.129.222.124:8080",
        help="Базовый URL стенда или локального web",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Гонять кейсы с needs_llm (дорого по токенам, 1–3 мин)",
    )
    parser.add_argument("--only", default="", help="Список id через запятую")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    results: list[dict] = []

    for case in cases:
        cid = case["id"]
        if only and cid not in only:
            continue
        if cid == "S5-health":
            results.append(_run_health(args.base_url, case))
            continue
        if cid == "S4-confirm-gate":
            results.append(_run_confirm_gate(case))
            continue
        if case.get("needs_llm") and not args.llm:
            results.append(
                {
                    "id": cid,
                    "ok": True,
                    "fails": [],
                    "skipped": True,
                    "reason": "нужен флаг --llm",
                }
            )
            continue

        body = {
            "vehicle_id": case["vehicle_id"],
            "message": case.get("user_message") or "разбери",
        }
        if case.get("session_id"):
            body["session_id"] = case["session_id"]
        payload = _request(
            args.base_url,
            "POST",
            "/api/consult",
            body,
            timeout=int(case.get("timeout_sec") or 120),
        )
        if payload.get("error") and "answer" not in payload:
            results.append(
                {
                    "id": cid,
                    "ok": False,
                    "fails": [str(payload.get("error")), str(payload.get("detail") or "")],
                    "skipped": False,
                }
            )
            continue
        fails = _check_case(case, payload)
        results.append(
            {
                "id": cid,
                "ok": not fails,
                "fails": fails,
                "skipped": False,
                "draft": bool(payload.get("draft")),
                "draft_notice": payload.get("draft_notice"),
                "repair_steps": len(payload.get("repair_steps") or []),
                "tools": _tools(payload.get("steps") or []),
                "usage": payload.get("usage"),
                "answer_preview": (payload.get("answer") or "")[:240],
            }
        )

    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPORTS / f"eval-smoke-{stamp}.json"
    summary = {
        "at": stamp,
        "base_url": args.base_url,
        "llm": args.llm,
        "passed": sum(1 for r in results if r["ok"] and not r.get("skipped")),
        "failed": sum(1 for r in results if not r["ok"]),
        "skipped": sum(1 for r in results if r.get("skipped")),
        "results": results,
    }
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"passed={summary['passed']} failed={summary['failed']} skipped={summary['skipped']}")
    print(f"report={out}")
    for row in results:
        mark = "SKIP" if row.get("skipped") else ("OK" if row["ok"] else "FAIL")
        extra = ""
        if row.get("fails"):
            extra = " · " + "; ".join(row["fails"][:3])
        if row.get("reason"):
            extra = " · " + row["reason"]
        print(f"  [{mark}] {row['id']}{extra}")
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
