from types import SimpleNamespace

import pandas as pd

from agents import pipeline, schema_agent, validator_agent
from eval.run_eval import _normalise_value


def test_schema_agent_falls_back_on_invalid_json(monkeypatch):
    schema = {
        "customer": [
            {"name": "c_custkey", "type": "BIGINT", "key": "PRI"},
            {"name": "c_name", "type": "VARCHAR", "key": None},
        ]
    }
    monkeypatch.setattr(schema_agent, "_full_schema", lambda: schema)
    monkeypatch.setattr(
        schema_agent,
        "chat",
        lambda messages: SimpleNamespace(content="not valid json"),
    )
    schema_agent._cached_relevant_schema.cache_clear()

    summary = schema_agent.get_relevant_schema("Count customers")

    assert "customer(c_custkey BIGINT [key], c_name VARCHAR)" in summary


def test_validator_flags_empty_result(monkeypatch):
    monkeypatch.setattr(
        validator_agent,
        "chat",
        lambda messages: SimpleNamespace(content='{"ok":true,"feedback":""}'),
    )

    result = validator_agent.validate(
        "Count rows", "SELECT id FROM customer", pd.DataFrame(columns=["id"])
    )

    assert result["ok"] is False
    assert "returned no rows" in result["feedback"]


def test_pipeline_retries_at_most_max_validator_retries(monkeypatch):
    calls = {"sql": 0, "validator": 0}

    def fake_answer_question(question, **kwargs):
        calls["sql"] += 1
        return {
            "answer": "A result",
            "sql": "SELECT 1",
            "dataframe": pd.DataFrame({"value": [1]}),
            "steps": [],
            "llm_calls": 1,
            "error": None,
        }

    def fake_validate(question, sql, result):
        calls["validator"] += 1
        return {"ok": False, "feedback": "Use the right grouping."}

    monkeypatch.setattr(pipeline, "answer_question", fake_answer_question)
    monkeypatch.setattr(pipeline, "validate", fake_validate)

    result = pipeline.run_pipeline(
        "Question",
        {"schema_agent": False, "validator": True, "max_validator_retries": 2},
    )

    assert calls == {"sql": 3, "validator": 3}
    assert result["error"].startswith("Validation failed after 3 attempt(s)")


def test_eval_normalizes_midnight_timestamps_as_dates():
    from datetime import date, datetime

    assert _normalise_value(datetime(1995, 1, 1)) == _normalise_value(date(1995, 1, 1))
