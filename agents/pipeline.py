import time

from agents.schema_agent import get_relevant_schema_with_calls
from agents.sql_agent import answer_question
from agents.validator_agent import validate


def _agent_trace(name, input_summary, output_summary, seconds, llm_calls):
    return {
        "agent_name": name,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "seconds": seconds,
        "llm_calls_used": llm_calls,
    }


def _result_template():
    return {
        "answer": "",
        "sql": None,
        "dataframe": None,
        "steps": [],
        "error": None,
        "llm_calls": 0,
        "agents_used": [],
        "agents_trace": [],
    }


def run_pipeline(question, config=None):
    """Run the configured schema -> SQL -> validator pipeline."""
    config = config or {}
    use_schema = bool(config.get("schema_agent", False))
    use_validator = bool(config.get("validator", False))
    retries = max(0, int(config.get("max_validator_retries", 0)))
    max_steps = max(1, int(config.get("max_steps", 8)))
    result = _result_template()
    schema_summary = None
    schema_calls = 0

    if use_schema:
        started = time.perf_counter()
        try:
            schema_summary, schema_calls = get_relevant_schema_with_calls(question)
            result["agents_used"].append("schema_agent")
            result["llm_calls"] += schema_calls
            summary = f"Selected schema summary ({len(schema_summary)} characters)."
        except Exception as error:
            summary = f"Schema selection failed; using default schema ({type(error).__name__})."
        result["agents_trace"].append(
            _agent_trace(
                "schema_agent",
                question[:160],
                summary,
                time.perf_counter() - started,
                schema_calls,
            )
        )

    feedback = None
    validation_failed = False
    attempts = retries + 1 if use_validator else 1
    for attempt in range(1, attempts + 1):
        validation_failed = False
        started = time.perf_counter()
        sql_result = answer_question(
            question,
            max_steps=max_steps,
            schema_summary=schema_summary,
            feedback=feedback,
        )
        sql_calls = sql_result.get("llm_calls", 0)
        result["llm_calls"] += sql_calls
        result["agents_used"].append("sql_agent")
        result["steps"].extend(sql_result.get("steps", []))
        result.update(
            answer=sql_result.get("answer", ""),
            sql=sql_result.get("sql"),
            dataframe=sql_result.get("dataframe"),
            error=sql_result.get("error"),
        )
        result["agents_trace"].append(
            _agent_trace(
                "sql_agent",
                f"Question: {question[:120]}" + (f"; retry {attempt}" if attempt > 1 else ""),
                sql_result.get("answer", "")[:180] or str(sql_result.get("error") or "No answer."),
                time.perf_counter() - started,
                sql_calls,
            )
        )
        if sql_result.get("error") or not use_validator:
            break

        started = time.perf_counter()
        validation = validate(question, result["sql"], result["dataframe"])
        result["llm_calls"] += 1
        if "validator_agent" not in result["agents_used"]:
            result["agents_used"].append("validator_agent")
        result["agents_trace"].append(
            _agent_trace(
                "validator_agent",
                f"SQL result with {len(result['dataframe']) if result['dataframe'] is not None else 0} rows",
                "Accepted" if validation["ok"] else validation["feedback"][:180],
                time.perf_counter() - started,
                1,
            )
        )
        if validation["ok"]:
            break
        feedback = validation["feedback"]
        validation_failed = True

    if validation_failed:
        result["error"] = f"Validation failed after {attempts} attempt(s): {feedback}"
    result["agents_used"] = list(dict.fromkeys(result["agents_used"]))
    return result
