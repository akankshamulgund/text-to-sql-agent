from agents import pipeline, planner_agent


def test_bad_planner_json_falls_back_to_full_pipeline(monkeypatch):
    monkeypatch.setattr(
        planner_agent,
        "chat",
        lambda messages: {"content": "not valid json"},
    )

    result = planner_agent.plan("Count customers", "customer(c_custkey)")

    assert result["category"] == "complex"
    assert result["use_schema_agent"] is True
    assert result["use_validator"] is True
    assert "invalid" in result["reason"].lower()


def test_invalid_planner_json_enables_full_pipeline(monkeypatch):
    monkeypatch.setattr(pipeline, "build_schema_overview", lambda: "customer(c_custkey)")
    monkeypatch.setattr(pipeline, "plan", lambda question, overview: planner_agent._fallback())
    schema_calls = []
    monkeypatch.setattr(
        pipeline,
        "get_relevant_schema_with_calls",
        lambda question: (schema_calls.append(question) or "customer(c_custkey)", 0),
    )
    monkeypatch.setattr(
        pipeline,
        "answer_question",
        lambda question, **kwargs: {
            "answer": "One customer count.",
            "sql": "SELECT COUNT(*) FROM customer",
            "dataframe": __import__("pandas").DataFrame({"count": [1]}),
            "steps": [],
            "llm_calls": 1,
            "error": None,
        },
    )
    monkeypatch.setattr(pipeline, "validate", lambda *args: {"ok": True, "feedback": ""})

    result = pipeline.run_pipeline(
        "Count customers",
        {"planner": True, "schema_agent": False, "validator": False},
    )

    assert schema_calls == ["Count customers"]
    assert "schema_agent" in result["agents_used"]
    assert "validator_agent" in result["agents_used"]


def test_ambiguous_question_returns_clarification_without_sql(monkeypatch):
    monkeypatch.setattr(pipeline, "build_schema_overview", lambda: "orders(o_orderdate)")
    monkeypatch.setattr(
        pipeline,
        "plan",
        lambda question, overview: {
            "category": "ambiguous",
            "use_schema_agent": True,
            "use_validator": True,
            "clarifying_question": "Which year should I use?",
            "reason": "The time range is missing.",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "answer_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("SQL must not run")),
    )

    result = pipeline.run_pipeline("How many orders per month?", {"planner": True})

    assert result["needs_clarification"] is True
    assert result["clarifying_question"] == "Which year should I use?"
    assert result["sql"] is None
    assert result["llm_calls"] == 1


def test_off_topic_question_returns_polite_message_without_sql(monkeypatch):
    monkeypatch.setattr(pipeline, "build_schema_overview", lambda: "customer(c_custkey)")
    monkeypatch.setattr(
        pipeline,
        "plan",
        lambda question, overview: {
            "category": "off_topic",
            "use_schema_agent": False,
            "use_validator": False,
            "clarifying_question": None,
            "reason": "This is unrelated to the database.",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "answer_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("SQL must not run")),
    )

    result = pipeline.run_pipeline("Tell me a joke", {"planner": True})

    assert result["sql"] is None
    assert "only answer questions about data" in result["answer"].lower()
    assert result["agents_used"] == ["planner_agent"]


def test_simple_question_skips_schema_agent(monkeypatch):
    monkeypatch.setattr(pipeline, "build_schema_overview", lambda: "customer(c_custkey)")
    monkeypatch.setattr(
        pipeline,
        "plan",
        lambda question, overview: {
            "category": "simple",
            "use_schema_agent": False,
            "use_validator": False,
            "clarifying_question": None,
            "reason": "One-table count.",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "get_relevant_schema_with_calls",
        lambda question: (_ for _ in ()).throw(AssertionError("Schema selection must be skipped")),
    )
    monkeypatch.setattr(
        pipeline,
        "answer_question",
        lambda question, **kwargs: {
            "answer": "15,000 customers",
            "sql": "SELECT COUNT(*) FROM customer",
            "dataframe": None,
            "steps": [],
            "llm_calls": 1,
            "error": None,
        },
    )

    result = pipeline.run_pipeline(
        "How many customers are there?",
        {"planner": True, "schema_agent": True, "validator": True},
    )

    assert "schema_agent" not in result["agents_used"]
    assert "validator_agent" not in result["agents_used"]
    assert result["answer"] == "15,000 customers"
