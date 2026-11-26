"""Вызов LLM: сообщения, инструменты, токены. Формат диалога агента — Anthropic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import httpx

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    LLM_PROVIDER,
    MAX_OUTPUT_TOKENS,
    PRICE_PER_MTOK,
    YANDEX_API_KEY,
    YANDEX_MODEL_URI,
)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
YANDEX_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


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


def model_name() -> str:
    if LLM_PROVIDER == "yandex":
        return YANDEX_MODEL_URI.rsplit("/", 1)[-1]
    return ANTHROPIC_MODEL


def _cost(model: str, usage: Usage) -> float:
    input_price, output_price = PRICE_PER_MTOK.get(model, PRICE_PER_MTOK["claude-sonnet-5-5"])
    return (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1_000_000


def complete(system: str, messages: list[dict], tools: list[dict], model: str | None = None) -> Completion:
    if LLM_PROVIDER == "yandex":
        return _complete_yandex(system, messages, tools)
    return _complete_anthropic(system, messages, tools, model)


def _complete_anthropic(
    system: str, messages: list[dict], tools: list[dict], model: str | None = None
) -> Completion:
    chosen = model or ANTHROPIC_MODEL
    if not ANTHROPIC_API_KEY:
        raise ModelError("ANTHROPIC_API_KEY не задан")
    response = httpx.post(
        ANTHROPIC_URL,
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


def _anthropic_tools_to_yandex(tools: list[dict]) -> list[dict]:
    mapped: list[dict] = []
    for item in tools:
        mapped.append(
            {
                "function": {
                    "name": item["name"],
                    "description": item.get("description") or "",
                    "parameters": item.get("input_schema") or {"type": "object", "properties": {}},
                }
            }
        )
    return mapped


def _tool_ids_from_messages(messages: list[dict]) -> dict[str, str]:
    known: dict[str, str] = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use" and block.get("id") and block.get("name"):
                known[str(block["id"])] = str(block["name"])
    return known


def _anthropic_messages_to_yandex(system: str, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "text": system}]
    id_to_name = _tool_ids_from_messages(messages)
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "user" and isinstance(content, str):
            out.append({"role": "user", "text": content})
            continue
        if role == "assistant" and isinstance(content, list):
            tool_calls: list[dict] = []
            text_parts: list[str] = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text") or "")
                if block.get("type") == "tool_use":
                    tool_calls.append(
                        {
                            "functionCall": {
                                "name": block.get("name"),
                                "arguments": block.get("input") or {},
                            }
                        }
                    )
            if tool_calls:
                out.append({"role": "assistant", "toolCallList": {"toolCalls": tool_calls}})
            elif text_parts:
                out.append({"role": "assistant", "text": "".join(text_parts)})
            continue
        if role == "user" and isinstance(content, list):
            results: list[dict] = []
            for block in content:
                if block.get("type") != "tool_result":
                    continue
                tool_id = str(block.get("tool_use_id") or "")
                name = id_to_name.get(tool_id, "tool")
                results.append(
                    {
                        "functionResult": {
                            "name": name,
                            "content": block.get("content") or "",
                        }
                    }
                )
            if results:
                out.append({"role": "user", "toolResultList": {"toolResults": results}})
    return out


def _yandex_response_to_completion(body: dict) -> Completion:
    alternative = (body.get("result") or {}).get("alternatives") or []
    if not alternative:
        raise ModelError("пустой ответ модели")
    message = alternative[0].get("message") or {}
    tool_uses: list[dict] = []
    text = message.get("text") or ""
    tool_call_list = message.get("toolCallList") or {}
    for call in tool_call_list.get("toolCalls") or []:
        function = call.get("functionCall") or {}
        tool_id = f"call_{uuid.uuid4().hex[:12]}"
        tool_uses.append(
            {
                "type": "tool_use",
                "id": tool_id,
                "name": function.get("name"),
                "input": function.get("arguments") or {},
            }
        )
    blocks: list[dict] = []
    if text:
        blocks.append({"type": "text", "text": text})
    blocks.extend(tool_uses)
    usage_raw = (body.get("result") or {}).get("usage") or {}
    usage = Usage(
        input_tokens=int(usage_raw.get("inputTextTokens") or usage_raw.get("input_text_tokens") or 0),
        output_tokens=int(usage_raw.get("completionTokens") or usage_raw.get("completion_tokens") or 0),
    )
    short_model = YANDEX_MODEL_URI.rsplit("/", 1)[-1]
    usage.cost_usd = round(_cost(short_model, usage), 6)
    return Completion(
        text=text,
        tool_uses=tool_uses,
        content=blocks,
        usage=usage,
        stop_reason="tool_use" if tool_uses else "end_turn",
        raw_blocks=blocks,
    )


def _complete_yandex(system: str, messages: list[dict], tools: list[dict]) -> Completion:
    if not YANDEX_API_KEY:
        raise ModelError("YANDEX_API_KEY не задан")
    if not YANDEX_MODEL_URI:
        raise ModelError("YANDEX_FOLDER_ID не задан (нужен для modelUri)")
    payload = {
        "modelUri": YANDEX_MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": str(MAX_OUTPUT_TOKENS),
        },
        "messages": _anthropic_messages_to_yandex(system, messages),
        "tools": _anthropic_tools_to_yandex(tools),
    }
    response = httpx.post(
        YANDEX_URL,
        headers={
            "Authorization": f"Api-Key {YANDEX_API_KEY}",
            "content-type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    if response.status_code >= 400:
        detail = response.text[:300]
        raise ModelError(f"модель ответила {response.status_code}: {detail}")
    return _yandex_response_to_completion(response.json())