from guardrails.sql_guard import validate_sql
from tools.query_tools import run_sql


def test_valid_select_works():
    result = run_sql("SELECT 1 AS value")

    assert result["ok"] is True
    assert result["data"]["rows"] == [[1]]


def test_drop_table_is_rejected():
    result = run_sql("DROP TABLE lineitem")

    assert result["ok"] is False
    assert "SELECT or WITH" in result["error"]


def test_multiple_statements_are_rejected():
    result = run_sql("SELECT 1; SELECT 2")

    assert result["ok"] is False
    assert "one SQL statement" in result["error"]


def test_limit_is_added():
    ok, cleaned_sql = validate_sql("SELECT 1 AS value")

    assert ok is True
    assert "LIMIT 1000" in cleaned_sql.upper()


def test_unknown_table_returns_clean_error():
    result = run_sql("SELECT * FROM missing_table")

    assert result["ok"] is False
    assert "SQL execution failed" in result["error"]
