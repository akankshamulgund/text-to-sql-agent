"""Startup helpers for a fresh Streamlit deployment."""

from pathlib import Path

from data.load_data import build_database


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "analytics.duckdb"


def ensure_database():
    """Build the public sample database once when no local copy exists."""
    if not DATABASE_PATH.exists():
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        build_database(DATABASE_PATH)
