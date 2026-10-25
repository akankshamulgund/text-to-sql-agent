import argparse
from collections import Counter
import json
import math
import os
import sys
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.pipeline import run_pipeline
from tools.query_tools import run_sql


CONFIGS = {
    "v0": {"schema_agent": False, "validator": False, "max_validator_retries": 0},
    "v1": {"schema_agent": True, "validator": False, "max_validator_retries": 0},
    "v2": {"schema_agent": False, "validator": True, "max_validator_retries": 2},
    "v3": {"schema_agent": True, "validator": True, "max_validator_retries": 2},
    "v5": {
        "planner": True,
        "schema_agent": True,
        "validator": True,
        "insight": True,
        "viz_agent": True,
        "max_validator_retries": 2,
    },
}
QUESTIONS_PATH = PROJECT_ROOT / "eval" / "questions.json"
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
RUNNER_VERSION = 2
MODEL_ID = os.getenv("LLM_MODEL", "unknown")


def _normalise_value(value):
    if value is None or (not isinstance(value, (list, tuple, dict)) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        if value.time().replace(tzinfo=None).isoformat() == "00:00:00":
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 8) if math.isfinite(value) else str(value)
    if hasattr(value, "item"):
        return _normalise_value(value.item())
    return str(value)


def _canonical_rows(dataframe):
    if dataframe is None:
        return None
    rows = [
        [_normalise_value(value) for value in row]
        for row in dataframe.itertuples(index=False, name=None)
    ]
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))


def _frames_match(actual, expected):
    return (
        actual is not None
        and expected is not None
        and _canonical_rows(actual) == _canonical_rows(expected)
    )


def _frame_for_sql(query):
    if not query:
        return None
    result = run_sql(query)
    if not result.get("ok"):
        return None
    data = result["data"]
    return pd.DataFrame(data["rows"], columns=data["columns"])


def _failure_category(result, accurate):
    error = result.get("error") or ""
    if "429" in error or "503" in error:
        return "rate_limit_or_unavailable"
    if "Validator" in error or "validation" in error.lower():
        return "validator_rejected"
    if error:
        return "agent_error"
    if result.get("dataframe") is None:
        return "no_result"
    return None if accurate else "execution_mismatch"


def _summary(config_name, records):
    evaluated = [record for record in records if record.get("completed")]
    scored = [record for record in evaluated if record.get("planner_category") != "ambiguous"]
    total = len(scored)
    correct = sum(bool(record.get("accuracy")) for record in scored)
    by_difficulty = {}
    for difficulty in sorted({record["difficulty"] for record in evaluated}):
        all_group = [record for record in evaluated if record["difficulty"] == difficulty]
        group = [record for record in all_group if record.get("planner_category") != "ambiguous"]
        by_difficulty[difficulty] = {
            "correct": sum(bool(record.get("accuracy")) for record in group),
            "total": len(group),
            "accuracy": sum(bool(record.get("accuracy")) for record in group) / len(group) if group else 0.0,
            "ambiguous": sum(record.get("planner_category") == "ambiguous" for record in all_group),
        }
    failures = {}
    for record in scored:
        category = record.get("failure_category")
        if category:
            failures[category] = failures.get(category, 0) + 1
    route_counts = Counter(record.get("planner_category") or "not_routed" for record in evaluated)
    route_fractions = {
        category: count / len(evaluated) if evaluated else 0.0
        for category, count in sorted(route_counts.items())
    }
    return {
        "config": config_name,
        "runner_version": RUNNER_VERSION,
        "model": MODEL_ID,
        "config_options": CONFIGS[config_name],
        "accuracy_overall": {"correct": correct, "total": total, "accuracy": correct / total if total else 0.0},
        "accuracy_by_difficulty": by_difficulty,
        "ambiguous_question_count": sum(record.get("planner_category") == "ambiguous" for record in evaluated),
        "routing_categories": {"counts": dict(route_counts), "fractions": route_fractions},
        "average_llm_calls_per_question": sum(record.get("llm_calls", 0) for record in evaluated) / len(evaluated) if evaluated else 0.0,
        "average_seconds_per_question": sum(record.get("seconds", 0.0) for record in evaluated) / total if total else 0.0,
        "failure_categories": failures,
        "results": records,
    }


def _save(path, config_name, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_summary(config_name, records), indent=2, default=str), encoding="utf-8")


def run(config_name, limit=None, resume=False, delay=2.0):
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    if limit is not None:
        questions = questions[:max(0, limit)]
    result_path = RESULTS_DIR / f"{config_name}.json"
    records = []
    completed_ids = set()
    if resume and result_path.exists():
        previous = json.loads(result_path.read_text(encoding="utf-8"))
        if previous.get("runner_version") == RUNNER_VERSION and previous.get("model") == MODEL_ID:
            records = previous.get("results", [])
        else:
            print("Existing checkpoint uses a different runner version or model; starting fresh.")
        current_gold = {item["id"]: item["gold_sql"] for item in questions}
        for record in records:
            if record.get("completed") and record.get("gold_sql") == current_gold.get(record["id"]):
                actual_frame = _frame_for_sql(record.get("sql"))
                expected_frame = _frame_for_sql(current_gold[record["id"]])
                record["accuracy"] = _frames_match(actual_frame, expected_frame)
                if not record.get("error"):
                    record["failure_category"] = None if record["accuracy"] else "execution_mismatch"
        completed_ids = {
            record["id"] for record in records
            if record.get("completed")
            and record.get("gold_sql") == current_gold.get(record["id"])
        }

    for index, item in enumerate(questions):
        if item["id"] in completed_ids:
            continue
        started = time.perf_counter()
        result = run_pipeline(item["question"], CONFIGS[config_name])
        gold = run_sql(item["gold_sql"])
        gold_frame = None
        if gold.get("ok"):
            data = gold["data"]
            gold_frame = pd.DataFrame(data["rows"], columns=data["columns"])
        planner_decision = result.get("planner_decision") or {}
        planner_category = planner_decision.get("category")
        is_ambiguous = planner_category == "ambiguous"
        accurate = False if is_ambiguous else _frames_match(result.get("dataframe"), gold_frame)
        error = result.get("error")
        rate_limited = "429" in (error or "") or "503" in (error or "")
        record = {
            "id": item["id"],
            "question": item["question"],
            "difficulty": item["difficulty"],
            "gold_sql": item["gold_sql"],
            "sql": result.get("sql"),
            "answer": result.get("answer"),
            "accuracy": bool(accurate),
            "failure_category": None if is_ambiguous else _failure_category(result, accurate),
            "planner_category": planner_category,
            "planner_decision": planner_decision,
            "error": error,
            "llm_calls": result.get("llm_calls", 0),
            "seconds": time.perf_counter() - started,
            "agents_used": result.get("agents_used", []),
            "completed": not rate_limited,
        }
        records = [existing for existing in records if existing.get("id") != item["id"]]
        records.append(record)
        _save(result_path, config_name, records)
        print(json.dumps({key: record[key] for key in ("id", "accuracy", "failure_category", "llm_calls", "seconds", "error")}, default=str))
        if rate_limited:
            print("Stopping after provider rate limit; rerun with --resume to continue later.")
            break
        if delay > 0 and index < len(questions) - 1:
            time.sleep(delay)

    summary = _summary(config_name, records)
    _save(result_path, config_name, records)
    print(json.dumps({key: summary[key] for key in (
        "config", "accuracy_overall", "accuracy_by_difficulty", "ambiguous_question_count", "routing_categories",
        "average_llm_calls_per_question", "average_seconds_per_question", "failure_categories",
    )}, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Evaluate SQL-agent configurations.")
    parser.add_argument("--config", choices=CONFIGS, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between questions (default: 2).")
    args = parser.parse_args()
    run(args.config, limit=args.limit, resume=args.resume, delay=args.delay)


if __name__ == "__main__":
    main()
