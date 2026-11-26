from app.llm import _anthropic_messages_to_yandex, _anthropic_tools_to_yandex


def test_yandex_tool_mapping() -> None:
    tools = [
        {
            "name": "get_check",
            "description": "Результат ML",
            "input_schema": {"type": "object", "properties": {"session_id": {"type": "string"}}},
        }
    ]
    out = _anthropic_tools_to_yandex(tools)
    assert out[0]["function"]["name"] == "get_check"
    assert out[0]["function"]["parameters"]["type"] == "object"


def test_yandex_message_mapping() -> None:
    messages = [
        {"role": "user", "content": "привет"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "tu1", "name": "get_check", "input": {"session_id": "s1"}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": '{"ok": true}'}],
        },
    ]
    out = _anthropic_messages_to_yandex("sys", messages)
    assert out[0] == {"role": "system", "text": "sys"}
    assert out[1]["text"] == "привет"
    assert out[2]["toolCallList"]["toolCalls"][0]["functionCall"]["name"] == "get_check"
    assert out[3]["toolResultList"]["toolResults"][0]["functionResult"]["name"] == "get_check"