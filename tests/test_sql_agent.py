from types import SimpleNamespace

from agents import sql_agent


def _tool_call(name, arguments, call_id="call-1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _message(content="", tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def test_loop_stops_when_final_answer_is_returned(monkeypatch):
    replies = iter([_message("Revenue is $42. <sql>SELECT 42</sql>")])
    monkeypatch.setattr(sql_agent, "chat", lambda *args, **kwargs: next(replies))

    result = sql_agent.answer_question("What is revenue?")

    assert result["answer"].startswith("Revenue is $42")
    assert result["sql"] == "SELECT 42"
    assert result["error"] is None


def test_loop_stops_at_max_steps(monkeypatch):
    monkeypatch.setattr(
        sql_agent,
        "chat",
        lambda *args, **kwargs: _message(
            tool_calls=[_tool_call("list_tables", "{}")]
        ),
    )
    monkeypatch.setitem(
        sql_agent.TOOL_FUNCTIONS,
        "list_tables",
        lambda: {"ok": True, "data": []},
    )

    result = sql_agent.answer_question("Count orders", max_steps=2)

    assert len(result["steps"]) == 2
    assert result["error"] == "Maximum agent steps reached (2)."


def test_tool_error_is_passed_back_to_model(monkeypatch):
    seen_messages = []

    def fake_chat(messages, tools=None):
        seen_messages.append(messages)
        if len(seen_messages) == 1:
            return _message(
                tool_calls=[_tool_call("describe_table", '{"name":"unknown"}')]
            )
        return _message("That table is unavailable. <sql>SELECT 1</sql>")

    monkeypatch.setattr(sql_agent, "chat", fake_chat)
    monkeypatch.setitem(
        sql_agent.TOOL_FUNCTIONS,
        "describe_table",
        lambda name: {"ok": False, "error": f"Unknown table: {name}"},
    )

    result = sql_agent.answer_question("Show unknown data")

    assert any(
        message["role"] == "tool"
        and "Unknown table: unknown" in message["content"]
        for message in seen_messages[1]
    )
    assert result["error"] is None
    assert len(result["steps"]) == 1
