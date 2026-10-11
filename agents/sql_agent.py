import json
import re
import time

import pandas as pd

from agents.llm import chat
from tools.query_tools import (
    describe_table,
    list_tables,
    run_sql,
    sample_rows,
)


SYSTEM_PROMPT = """You are a read-only DuckDB analytics SQL agent.
The following schema was inspected from this database; treat these table and
column names as verified. Do not spend calls re-describing it. Use list_tables,
describe_table, or sample_rows when you need additional verification or data.

customer(c_custkey, c_name, c_address, c_nationkey, c_phone, c_acctbal,
c_mktsegment, c_comment)
lineitem(l_orderkey, l_partkey, l_suppkey, l_linenumber, l_quantity,
l_extendedprice, l_discount, l_tax, l_returnflag, l_linestatus, l_shipdate,
l_commitdate, l_receiptdate, l_shipinstruct, l_shipmode, l_comment)
nation(n_nationkey, n_name, n_regionkey, n_comment)
orders(o_orderkey, o_custkey, o_orderstatus, o_totalprice, o_orderdate,
o_orderpriority, o_clerk, o_shippriority, o_comment)
part(p_partkey, p_name, p_mfgr, p_brand, p_type, p_size, p_container,
p_retailprice, p_comment)
partsupp(ps_partkey, ps_suppkey, ps_availqty, ps_supplycost, ps_comment)
region(r_regionkey, r_name, r_comment)
supplier(s_suppkey, s_name, s_address, s_nationkey, s_phone, s_acctbal,
s_comment)

Only use verified tables and columns; never guess names. Write DuckDB-compatible
SQL. Run the query, sanity-check its results, state any assumptions, and finish
with the final SQL inside <sql> and </sql> tags. Use tool errors to correct
queries. Do not claim results that were not returned by a tool. Keep answers
concise."""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List available database tables and their row counts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "Describe a table's columns, types, and key information.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sample_rows",
            "description": "Return up to 20 example rows from a table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "n": {"type": "integer"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "Validate and execute one read-only DuckDB SELECT query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


TOOL_FUNCTIONS = {
    "list_tables": list_tables,
    "describe_table": describe_table,
    "sample_rows": sample_rows,
    "run_sql": run_sql,
}


def _value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _summary(result):
    if not result.get("ok"):
        return str(result.get("error", "Tool failed."))
    data = result.get("data")
    if isinstance(data, dict) and "rows" in data:
        return f"Returned {len(data['rows'])} rows and columns {data.get('columns', [])}."
    if isinstance(data, list):
        return f"Returned {len(data)} items."
    return "Tool completed successfully."


def _extract_sql(text):
    match = re.search(r"<sql>\s*(.*?)\s*</sql>", text or "", re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def _empty_result(error=None, answer=""):
    return {
        "answer": answer,
        "sql": None,
        "dataframe": None,
        "steps": [],
        "error": error,
    }


def answer_question(question, max_steps=8):
    """Run a bounded tool-calling loop and return answer, SQL, data, and trace."""
    result = _empty_result()
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        successful_sql = None
        dataframe = None

        for step_number in range(1, max_steps + 1):
            message = chat(messages, tools=TOOLS)
            content = _value(message, "content") or ""
            tool_calls = _value(message, "tool_calls") or []
            assistant_message = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": _value(call, "id"),
                        "type": "function",
                        "function": {
                            "name": _value(_value(call, "function", {}), "name"),
                            "arguments": _value(_value(call, "function", {}), "arguments", "{}"),
                        },
                    }
                    for call in tool_calls
                ]
            messages.append(assistant_message)

            if not tool_calls:
                result.update(
                    answer=content,
                    sql=_extract_sql(content) or successful_sql,
                    dataframe=dataframe,
                    steps=result["steps"],
                    error=None,
                )
                return result

            for call in tool_calls:
                function = _value(call, "function", {})
                tool_name = _value(function, "name", "")
                raw_arguments = _value(function, "arguments", "{}")
                start_time = time.perf_counter()
                try:
                    arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                    tool_function = TOOL_FUNCTIONS.get(tool_name)
                    if tool_function is None:
                        tool_result = {"ok": False, "error": f"Unknown tool: {tool_name}"}
                    elif tool_name == "list_tables":
                        tool_result = tool_function()
                    else:
                        tool_result = tool_function(**arguments)
                except Exception as error:
                    arguments = raw_arguments
                    tool_result = {"ok": False, "error": f"Tool input or execution error: {error}"}
                elapsed = time.perf_counter() - start_time

                result["steps"].append(
                    {
                        "step": step_number,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result_summary": _summary(tool_result),
                        "seconds": elapsed,
                    }
                )
                if tool_name == "run_sql" and tool_result.get("ok"):
                    data = tool_result.get("data", {})
                    dataframe = pd.DataFrame(data.get("rows", []), columns=data.get("columns", []))
                    successful_sql = arguments.get("query")

                # Tool results are plain text so the model can read and correct errors.
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": _value(call, "id"),
                        "content": json.dumps(tool_result, default=str),
                    }
                )

        result.update(
            answer="I couldn't complete the analysis within the allowed number of steps.",
            sql=successful_sql,
            dataframe=dataframe,
            error=f"Maximum agent steps reached ({max_steps}).",
        )
        return result
    except Exception as error:
        result["error"] = f"The SQL agent could not complete the request: {error}"
        if not result["answer"]:
            result["answer"] = "I couldn't complete that analysis. Please try again."
        return result
