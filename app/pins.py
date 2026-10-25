import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from guardrails.sql_guard import validate_sql
from tools.query_tools import run_sql


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PINS_PATH = PROJECT_ROOT / "data" / "pins.json"


def _read_pins():
    if not PINS_PATH.exists():
        return []
    try:
        pins = json.loads(PINS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return pins if isinstance(pins, list) else []


def _write_pins(pins):
    PINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = PINS_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(pins, indent=2, default=str), encoding="utf-8")
    temporary_path.replace(PINS_PATH)


def add_pin(question, sql, chart_spec):
    pin = {
        "id": uuid.uuid4().hex,
        "question": question,
        "sql": sql,
        "chart_spec": chart_spec,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    pins = _read_pins()
    pins.append(pin)
    _write_pins(pins)
    return pin


def list_pins():
    return _read_pins()


def remove_pin(pin_id):
    pins = _read_pins()
    remaining = [pin for pin in pins if pin.get("id") != pin_id]
    if len(remaining) == len(pins):
        return False
    _write_pins(remaining)
    return True


@st.cache_data(show_spinner=False)
def run_pinned_query(sql):
    """Validate the saved SQL again before passing it to the database tool."""
    ok, cleaned_or_error = validate_sql(sql)
    if not ok:
        return {"ok": False, "error": cleaned_or_error}

    result = run_sql(cleaned_or_error)
    if not result.get("ok"):
        return result
    data = result.get("data", {})
    dataframe = pd.DataFrame(data.get("rows", []), columns=data.get("columns", []))
    return {"ok": True, "dataframe": dataframe}
