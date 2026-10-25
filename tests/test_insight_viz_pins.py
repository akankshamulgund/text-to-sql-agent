from types import SimpleNamespace

import pandas as pd
import pytest

from agents import insight_agent, viz_agent
from app import pins


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        '{"type":"bar","x":"missing","y":"amount","color":null,"title":"Bad columns"}',
    ],
)
def test_viz_agent_falls_back_to_rules(monkeypatch, content):
    monkeypatch.setattr(
        viz_agent,
        "chat",
        lambda messages: SimpleNamespace(content=content),
    )
    dataframe = pd.DataFrame({"month": ["2025-01-01", "2025-02-01"], "sales": [2, 3]})

    spec = viz_agent.choose_chart("Show sales by month", dataframe)

    assert spec["type"] == "line"
    assert spec["x"] == "month"
    assert spec["y"] == "sales"


def test_insight_handles_empty_dataframe(monkeypatch):
    seen = []

    def fake_chat(messages):
        seen.extend(messages)
        return SimpleNamespace(content="There is not enough data to summarize this result.")

    monkeypatch.setattr(insight_agent, "chat", fake_chat)
    summary = insight_agent.summarize(
        "Show recent orders", "SELECT order_id FROM orders WHERE false", pd.DataFrame(columns=["order_id"])
    )

    assert "not enough data" in summary.lower()
    assert '"result_row_count": 0' in seen[1]["content"]
    assert '"sample_rows": []' in seen[1]["content"]


def test_pins_can_be_added_listed_and_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(pins, "PINS_PATH", tmp_path / "pins.json")

    saved = pins.add_pin(
        "Show sales by month",
        "SELECT DATE '2025-01-01' AS month, 2 AS sales",
        {"type": "line", "x": "month", "y": "sales", "color": None, "title": "Sales"},
    )

    assert pins.list_pins() == [saved]
    assert pins.remove_pin(saved["id"]) is True
    assert pins.list_pins() == []
    assert pins.remove_pin(saved["id"]) is False


def test_guardrail_rejected_pin_never_executes(monkeypatch):
    executed = []
    monkeypatch.setattr(pins, "run_sql", lambda sql: executed.append(sql))
    pins.run_pinned_query.clear()

    result = pins.run_pinned_query("DROP TABLE customer")

    assert result["ok"] is False
    assert "SELECT or WITH" in result["error"]
    assert executed == []
