import json
import re

import pandas as pd
import sqlglot
from sqlglot import exp

from agents.llm import chat
from guardrails.sql_guard import validate_sql


def _result_frame(result):
    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, dict) and result.get("ok"):
        data = result.get("data") or {}
        return pd.DataFrame(data.get("rows", []), columns=data.get("columns", []))
    return pd.DataFrame()


def _rule_feedback(sql, result, dataframe):
    issues = []
    ok, cleaned_or_error = validate_sql(sql)
    if not ok:
        issues.append(f"SQL guard rejected the query: {cleaned_or_error}")

    if dataframe.empty:
        issues.append("The query returned no rows; check its joins and filters.")
    if len(dataframe) >= 1000:
        issues.append("The result reached the 1000-row LIMIT cap and may be truncated.")
    for column in dataframe.columns:
        if dataframe[column].isna().all():
            issues.append(f"Result column '{column}' contains only NULL values.")

    if isinstance(result, pd.DataFrame):
        row_count = len(result)
    elif isinstance(result, dict):
        row_count = len((result.get("data") or {}).get("rows", []))
    else:
        row_count = len(dataframe)
    if row_count >= 1000 and "The result reached the 1000-row LIMIT cap and may be truncated." not in issues:
        issues.append("The result reached the 1000-row LIMIT cap and may be truncated.")

    try:
        statement = sqlglot.parse_one(sql, read="duckdb")
        for join in statement.find_all(exp.Join):
            if not join.args.get("on") and not join.args.get("using"):
                issues.append("A JOIN has no ON or USING condition and may create a Cartesian product.")
                break
    except sqlglot.ParseError:
        pass
    return issues


def _sample_result(dataframe):
    if dataframe.empty:
        return {"columns": list(dataframe.columns), "rows": []}
    return {
        "columns": list(dataframe.columns),
        "rows": dataframe.head(5).where(pd.notna(dataframe.head(5)), None).to_dict(orient="records"),
    }


def _parse_llm_feedback(content):
    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", content or "", re.DOTALL)
        if not match:
            return True, ""
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return True, ""
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
        return True, ""
    feedback = payload.get("feedback", "")
    return payload["ok"], str(feedback) if feedback else ""


def validate(question, sql, result):
    """Check SQL safety and result quality, then ask the LLM to assess intent."""
    dataframe = _result_frame(result)
    rule_issues = _rule_feedback(sql or "", result, dataframe)
    sample = _sample_result(dataframe)
    llm_ok = True
    llm_feedback = ""
    try:
        response = chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Check whether the SQL answers the question with correct joins, "
                        "filters, aggregation, and output columns. Return JSON only: "
                        '{"ok":true|false,"feedback":"specific concise feedback"}.'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "sql": sql, "result_sample": sample},
                        default=str,
                    ),
                },
            ]
        )
        content = response.get("content", "") if isinstance(response, dict) else getattr(response, "content", "")
        llm_ok, llm_feedback = _parse_llm_feedback(content)
    except Exception:
        # Rule-based checks remain useful when the validator model is unavailable.
        pass

    feedback_items = rule_issues[:]
    if not llm_ok:
        feedback_items.append(llm_feedback or "The query may not answer the question correctly.")
    return {"ok": not feedback_items, "feedback": " ".join(feedback_items)}
