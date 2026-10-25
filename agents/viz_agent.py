import json
import re

import pandas as pd

from agents.llm import chat


CHART_TYPES = {"bar", "line", "pie", "scatter", "table", "metric"}


def _content(message):
    if isinstance(message, dict):
        return message.get("content") or ""
    return getattr(message, "content", "") or ""


def _looks_like_date(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_numeric_dtype(series) or series.empty:
        return False
    return pd.to_datetime(series, errors="coerce").notna().all()


def _fallback(question, dataframe):
    columns = list(dataframe.columns) if dataframe is not None else []
    title = question.strip() or "Query result"
    if dataframe is None or not columns:
        return {"type": "table", "x": None, "y": None, "color": None, "title": title}
    if len(dataframe) == 1 and len(columns) == 1:
        return {"type": "metric", "x": None, "y": columns[0], "color": None, "title": title}

    date_columns = [column for column in columns if _looks_like_date(dataframe[column])]
    numeric_columns = [column for column in columns if pd.api.types.is_numeric_dtype(dataframe[column])]
    if date_columns and numeric_columns:
        return {"type": "line", "x": date_columns[0], "y": numeric_columns[0], "color": None, "title": title}
    if len(columns) == 2 and len(numeric_columns) == 1:
        x_column = next(column for column in columns if column != numeric_columns[0])
        return {"type": "bar", "x": x_column, "y": numeric_columns[0], "color": None, "title": title}
    return {"type": "table", "x": None, "y": None, "color": None, "title": title}


def _parse_spec(content, columns):
    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", content or "", re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict) or payload.get("type") not in CHART_TYPES:
        return None

    spec = {
        "type": payload["type"],
        "x": payload.get("x"),
        "y": payload.get("y"),
        "color": payload.get("color"),
        "title": str(payload.get("title") or "Query result"),
    }
    if any(column is not None and column not in columns for column in (spec["x"], spec["y"], spec["color"])):
        return None
    if spec["type"] == "metric" and spec["y"] is None:
        return None
    if spec["type"] in {"bar", "line", "pie", "scatter"} and (spec["x"] is None or spec["y"] is None):
        return None
    return spec


def choose_chart(question, dataframe):
    """Ask the model for a chart specification and validate its column choices."""
    columns = [] if dataframe is None else list(dataframe.columns)
    metadata = {
        "columns": [
            {"name": column, "dtype": str(dataframe[column].dtype)}
            for column in columns
        ],
        "sample_rows": [] if dataframe is None else dataframe.head(5).where(dataframe.head(5).notna(), None).to_dict(orient="records"),
    }
    response = chat(
        [
            {
                "role": "system",
                "content": (
                    "Choose a useful chart for the question and result. Return JSON only with "
                    'keys type, x, y, color, title. type must be bar, line, pie, scatter, table, or metric. '
                    "Use only supplied column names; set unused columns to null."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"question": question, **metadata}, default=str),
            },
        ]
    )
    return _parse_spec(_content(response), columns) or _fallback(question, dataframe)
