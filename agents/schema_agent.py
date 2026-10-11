import json
from functools import lru_cache

from agents.llm import chat
from tools.query_tools import describe_table, list_tables


JOIN_HINTS = (
    "orders.o_custkey = customer.c_custkey",
    "customer.c_nationkey = nation.n_nationkey",
    "nation.n_regionkey = region.r_regionkey",
    "lineitem.l_orderkey = orders.o_orderkey",
    "lineitem.l_partkey = part.p_partkey",
    "lineitem.l_suppkey = supplier.s_suppkey",
    "partsupp.ps_partkey = part.p_partkey",
    "partsupp.ps_suppkey = supplier.s_suppkey",
)
PRIMARY_KEY_COLUMNS = {
    "customer": {"c_custkey"},
    "lineitem": {"l_orderkey", "l_linenumber"},
    "nation": {"n_nationkey"},
    "orders": {"o_orderkey"},
    "part": {"p_partkey"},
    "partsupp": {"ps_partkey", "ps_suppkey"},
    "region": {"r_regionkey"},
    "supplier": {"s_suppkey"},
}


def _content(message):
    return message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")


@lru_cache(maxsize=1)
def _full_schema():
    """Build and cache the full schema from the read-only database tools."""
    table_result = list_tables()
    if not table_result.get("ok"):
        raise RuntimeError(table_result.get("error", "Could not list database tables."))

    schema = {}
    for table in table_result["data"]:
        name = table["name"]
        description = describe_table(name)
        if not description.get("ok"):
            raise RuntimeError(description.get("error", f"Could not describe {name}."))
        schema[name] = description["data"]["columns"]
    return schema


def _format_schema(schema, table_names=None, selected_columns=None):
    table_names = list(schema) if table_names is None else table_names
    included = set(table_names)
    hints = [
        hint for hint in JOIN_HINTS
        if hint.split(".", 1)[0] in included
        and hint.split(" = ", 1)[1].split(".", 1)[0] in included
    ]
    join_columns = {table_name: set() for table_name in included}
    for hint in hints:
        left, right = hint.split(" = ")
        left_table, left_column = left.split(".")
        right_table, right_column = right.split(".")
        join_columns[left_table].add(left_column)
        join_columns[right_table].add(right_column)

    lines = []
    for table_name in table_names:
        columns = schema.get(table_name)
        if not columns:
            continue
        selected = None if selected_columns is None else set(selected_columns.get(table_name, []))
        visible = [
            column for column in columns
            if selected is None
            or column["name"] in selected
            or column.get("key")
            or column["name"] in PRIMARY_KEY_COLUMNS.get(table_name, set())
            or column["name"] in join_columns.get(table_name, set())
        ]
        rendered = [
            f"{column['name']} {column['type']}"
            + (" [key]" if column.get("key") or column["name"] in PRIMARY_KEY_COLUMNS.get(table_name, set()) else "")
            for column in visible
        ]
        lines.append(f"{table_name}({', '.join(rendered)})")

    if hints:
        lines.append("Join hints: " + "; ".join(hints))
    return "\n".join(lines)


def _parse_selection(content, schema):
    try:
        selected = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(selected, dict) or not isinstance(selected.get("tables"), list):
        return None

    table_names = []
    selected_columns = {}
    for item in selected["tables"]:
        if isinstance(item, str):
            name, columns = item, []
        elif isinstance(item, dict):
            name = item.get("name")
            columns = item.get("columns", [])
        else:
            continue
        if name not in schema or not isinstance(columns, list):
            continue
        valid_columns = {column["name"] for column in schema[name]}
        selected_columns[name] = [column for column in columns if column in valid_columns]
        if name not in table_names:
            table_names.append(name)

    if not table_names:
        return None
    return _format_schema(schema, table_names, selected_columns)


@lru_cache(maxsize=256)
def _cached_relevant_schema(question):
    schema = _full_schema()
    full_summary = _format_schema(schema)
    try:
        response = chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Select only tables and columns relevant to the question. "
                        "Return JSON only in this shape: "
                        '{"tables":[{"name":"table_name","columns":["column_name"]}]}.'
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nFull schema:\n{full_summary}",
                },
            ]
        )
        relevant = _parse_selection(_content(response), schema)
        return relevant or full_summary
    except Exception:
        return full_summary


def get_relevant_schema(question):
    """Return a cached, question-specific schema summary or the full schema."""
    return _cached_relevant_schema(question)


def get_relevant_schema_with_calls(question):
    """Return the cached schema and whether this request performed an LLM call."""
    before = _cached_relevant_schema.cache_info()
    summary = _cached_relevant_schema(question)
    after = _cached_relevant_schema.cache_info()
    return summary, int(after.misses > before.misses)
