import json
import re

from agents.llm import chat
from tools.query_tools import describe_table, list_tables


CATEGORIES = {"simple", "complex", "ambiguous", "off_topic"}


def build_schema_overview():
    """Build a compact overview with table names and one-line column lists."""
    tables_result = list_tables()
    if not tables_result.get("ok"):
        return ""

    lines = []
    for table in tables_result.get("data", []):
        name = table.get("name")
        description = describe_table(name)
        if not description.get("ok"):
            continue
        columns = [column["name"] for column in description["data"].get("columns", [])]
        lines.append(f"{name}({', '.join(columns)})")
    return "\n".join(lines)


def _fallback():
    return {
        "category": "complex",
        "use_schema_agent": True,
        "use_validator": True,
        "clarifying_question": None,
        "reason": "Planner output was invalid; using the full pipeline.",
    }


def _content(message):
    if isinstance(message, dict):
        return message.get("content") or ""
    return getattr(message, "content", "") or ""


def _parse_plan(content):
    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", content or "", re.DOTALL)
        if not match:
            return _fallback()
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return _fallback()

    if not isinstance(payload, dict):
        return _fallback()
    category = payload.get("category")
    use_schema = payload.get("use_schema_agent")
    use_validator = payload.get("use_validator")
    clarification = payload.get("clarifying_question")
    reason = payload.get("reason")
    if (
        category not in CATEGORIES
        or not isinstance(use_schema, bool)
        or not isinstance(use_validator, bool)
        or (clarification is not None and not isinstance(clarification, str))
        or not isinstance(reason, str)
        or (category == "ambiguous" and not clarification)
    ):
        return _fallback()

    return {
        "category": category,
        "use_schema_agent": use_schema,
        "use_validator": use_validator,
        "clarifying_question": clarification,
        "reason": reason,
    }


def plan(question, schema_overview):
    """Classify a question and choose an economical pipeline configuration."""
    messages = [
        {
            "role": "system",
            "content": (
                "Route analytics questions using only the supplied database overview. "
                "simple means one table and no joins. complex means joins, multiple "
                "aggregations, or date logic. ambiguous means a key detail such as the "
                "metric, time range, or ranking criterion is missing and no sensible "
                "default is obvious. off_topic means the database cannot answer it. "
                "For simple questions prefer use_schema_agent=false and use_validator=false; "
                "for complex questions prefer both true. Return JSON only with keys "
                "category, use_schema_agent, use_validator, clarifying_question, reason."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nSchema overview:\n{schema_overview}",
        },
    ]
    try:
        return _parse_plan(_content(chat(messages)))
    except Exception:
        return _fallback()
