from pathlib import Path

import duckdb


DATABASE_PATH = Path(__file__).with_name("analytics.duckdb")


def build_database(database_path=DATABASE_PATH):
    """Create the small public TPC-H sample database used by the demo."""
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("INSTALL tpch")
        connection.execute("LOAD tpch")
        connection.execute("CALL dbgen(sf=0.1)")
    finally:
        connection.close()


def main():
    build_database()


if __name__ == "__main__":
    main()
