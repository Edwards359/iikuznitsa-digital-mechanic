"""Тонкий вызов Anthropic: сообщения, инструменты, токены. Без логики агента."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, MAX_OUTPUT_TOKENS, PRICE_PER_MTOK

API_URL = "https://api.anthropic.com/v1/messages"


class ModelError(RuntimeError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class Completion:
    text: str
    tool_uses: list[dict]
    content: list[dict]
    usage: Usage
    stop_reason: str
    raw_blocks: list[dict] = field(default_factory=list)


def _cost(model: str, usage: Usage) -> float:
    input_price, output_price = PRICE_PER_MTOK.get(model, PRICE_PER_MTOK["claude-sonnet-5-5"])
    return (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1_000_000


def complete(system: str, messages: list[dict], tools: list[dict], model: str | None = None) -> Completion:
    chosen = model or ANTHROPIC_MODEL
    if not ANTHROPIC_API_KEY:
        raise ModelError("ANTHROPIC_API_KEY не задан")
    response = httpx.post(
        API_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": chosen,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": system,
            "messages": messages,
            "tools": tools,
        },
        timeout=90,
    )
    if response.status_code >= 400:
        raise ModelError(f"модель ответила {response.status_code}")
    body = response.json()
    blocks = body.get("content") or []
    text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    tool_uses = [block for block in blocks if block.get("type") == "tool_use"]
    raw_usage = body.get("usage") or {}
    usage = Usage(
        input_tokens=int(raw_usage.get("input_tokens") or 0),
        output_tokens=int(raw_usage.get("output_tokens") or 0),
    )
    usage.cost_usd = round(_cost(chosen, usage), 6)
    return Completion(
        text=text,
        tool_uses=tool_uses,
        content=blocks,
        usage=usage,
        stop_reason=body.get("stop_reason") or "",
        raw_blocks=blocks,
    )
