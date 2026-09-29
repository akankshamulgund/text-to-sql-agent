from pathlib import Path

import duckdb


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "analytics.duckdb"


def get_connection():
    """Open the analytics database without write access."""
    return duckdb.connect(str(DATABASE_PATH), read_only=True)
