from pathlib import Path

import duckdb


DATABASE_PATH = Path(__file__).with_name("analytics.duckdb")


def main():
    connection = duckdb.connect(str(DATABASE_PATH))
    try:
        connection.execute("INSTALL tpch")
        connection.execute("LOAD tpch")
        connection.execute("CALL dbgen(sf=0.1)")

        tables = connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchall()
        for (table_name,) in tables:
            count = connection.execute(
                f'SELECT COUNT(*) FROM "{table_name.replace(chr(34), chr(34) * 2)}"'
            ).fetchone()[0]
            print(f"{table_name}: {count} rows")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
