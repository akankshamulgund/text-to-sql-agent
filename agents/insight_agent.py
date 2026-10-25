import json

from agents.llm import chat


def _content(message):
    if isinstance(message, dict):
        return message.get("content") or ""
    return getattr(message, "content", "") or ""


def summarize(question, sql, dataframe):
    """Return a concise, data-grounded summary of a query result."""
    row_count = 0 if dataframe is None else len(dataframe)
    sample_rows = []
    if dataframe is not None and not dataframe.empty:
        sample_rows = dataframe.head(20).where(dataframe.head(20).notna(), None).to_dict(orient="records")

    response = chat(
        [
            {
                "role": "system",
                "content": (
                    "Summarize the query result in 2 to 3 sentences of plain English. "
                    "Use only facts present in the result. Mention notable points such "
                    "as the top value, trend direction, or outliers when visible. Do not "
                    "invent causes. If the result is empty, say 'not enough data'."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "sql": sql,
                        "result_row_count": row_count,
                        "sample_rows": sample_rows,
                    },
                    default=str,
                ),
            },
        ]
    )
    return _content(response).strip()
