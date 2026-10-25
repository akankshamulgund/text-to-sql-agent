import time

from agents.planner_agent import build_schema_overview, plan
from agents.schema_agent import get_relevant_schema_with_calls
from agents.insight_agent import summarize
from agents.sql_agent import answer_question
from agents.validator_agent import validate
from agents.viz_agent import choose_chart


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
        "insight": None,
        "chart_spec": None,
        "needs_clarification": False,
        "clarifying_question": None,
        "planner_decision": None,
        "total_seconds": 0.0,
        "estimated_tokens": 0,
        "agents_used": [],
        "agents_trace": [],
    }


def run_pipeline(question, config=None):
    """Run the configured schema -> SQL -> validator pipeline."""
    config = config or {}
    started_pipeline = time.perf_counter()
    use_planner = bool(config.get("planner", False))
    use_schema = bool(config.get("schema_agent", False))
    use_validator = bool(config.get("validator", False))
    use_insight = bool(config.get("insight", False))
    use_viz = bool(config.get("viz_agent", False))
    retries = max(0, int(config.get("max_validator_retries", 0)))
    max_steps = max(1, int(config.get("max_steps", 8)))
    result = _result_template()
    schema_summary = None
    schema_calls = 0

    if use_planner:
        started = time.perf_counter()
        schema_overview = build_schema_overview()
        decision = plan(question, schema_overview)
        result["llm_calls"] += 1
        result["planner_decision"] = decision
        result["agents_used"].append("planner_agent")
        result["agents_trace"].append(
            _agent_trace(
                "planner_agent",
                f"Question: {question[:120]}; schema overview: {len(schema_overview)} characters",
                f"{decision['category']}: {decision['reason']}",
                time.perf_counter() - started,
                1,
            )
        )
        if decision["category"] == "ambiguous":
            result["needs_clarification"] = True
            result["clarifying_question"] = decision["clarifying_question"]
            result["answer"] = decision["clarifying_question"] or "Could you clarify your question?"
            _finalize_trace(result, question, started_pipeline)
            return result
        if decision["category"] == "off_topic":
            result["answer"] = "I can only answer questions about data in this database. Please ask a question about its tables and fields."
            _finalize_trace(result, question, started_pipeline)
            return result

        if decision["reason"] == "Planner output was invalid; using the full pipeline.":
            use_schema = True
            use_validator = True
        else:
            use_schema = use_schema and decision["use_schema_agent"]
            use_validator = use_validator and decision["use_validator"]

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

    if result["error"] is None and result["dataframe"] is not None:
        optional_agents = []
        if use_insight:
            optional_agents.append(("insight_agent", summarize))
        if use_viz:
            optional_agents.append(("viz_agent", choose_chart))

        for agent_name, agent_function in optional_agents:
            started = time.perf_counter()
            output_summary = "Agent returned no output."
            result["agents_used"].append(agent_name)
            result["llm_calls"] += 1
            try:
                output = agent_function(question, result["sql"], result["dataframe"]) if agent_name == "insight_agent" else agent_function(question, result["dataframe"])
                if agent_name == "insight_agent":
                    result["insight"] = output
                    output_summary = output[:180]
                else:
                    result["chart_spec"] = output
                    output_summary = str(output)
            except Exception as error:
                output_summary = f"Unavailable ({type(error).__name__})."
            result["agents_trace"].append(
                _agent_trace(
                    agent_name,
                    question[:160],
                    output_summary,
                    time.perf_counter() - started,
                    1,
                )
            )

    result["agents_used"] = list(dict.fromkeys(result["agents_used"]))
    _finalize_trace(result, question, started_pipeline)
    return result


def _finalize_trace(result, question, started_pipeline):
    result["total_seconds"] = time.perf_counter() - started_pipeline
    visible_text = [question, result.get("answer") or "", result.get("sql") or ""]
    for trace in result["agents_trace"]:
        visible_text.extend((trace.get("input_summary", ""), trace.get("output_summary", "")))
    for step in result["steps"]:
        visible_text.extend((str(step.get("arguments", "")), step.get("result_summary", "")))
    # This is an approximate display metric, not provider-reported token billing.
    result["estimated_tokens"] = max(1, sum(len(text) for text in visible_text) // 4)
