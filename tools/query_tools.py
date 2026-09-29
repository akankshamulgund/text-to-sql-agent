import threading

from guardrails.sql_guard import validate_sql
from tools.db import get_connection


def _quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def _table_names(connection):
    return {
        row[0]
        for row in connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            """
        ).fetchall()
    }


def _check_table(connection, name):
    if not isinstance(name, str) or name not in _table_names(connection):
        return False, f"Unknown table: {name}"
    return True, None


def list_tables():
    connection = get_connection()
    try:
        tables = []
        for name in sorted(_table_names(connection)):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(name)}"
            ).fetchone()[0]
            tables.append({"name": name, "row_count": count})
        return {"ok": True, "data": tables}
    except Exception as error:
        return {"ok": False, "error": f"Could not list tables: {error}"}
    finally:
        connection.close()


def describe_table(name):
    connection = get_connection()
    try:
        valid, error = _check_table(connection, name)
        if not valid:
            return {"ok": False, "error": error}
        rows = connection.execute(
            f"DESCRIBE {_quote_identifier(name)}"
        ).fetchall()
        columns = [
            {
                "name": row[0],
                "type": row[1],
                "key": row[4] or None,
            }
            for row in rows
        ]
        return {"ok": True, "data": {"table": name, "columns": columns}}
    except Exception as error:
        return {"ok": False, "error": f"Could not describe table '{name}': {error}"}
    finally:
        connection.close()


def sample_rows(name, n=5):
    connection = get_connection()
    try:
        valid, error = _check_table(connection, name)
        if not valid:
            return {"ok": False, "error": error}
        try:
            row_limit = min(max(int(n), 0), 20)
        except (TypeError, ValueError):
            return {"ok": False, "error": "n must be an integer."}
        result = connection.execute(
            f"SELECT * FROM {_quote_identifier(name)} LIMIT {row_limit}"
        )
        return {
            "ok": True,
            "data": {
                "columns": [column[0] for column in result.description],
                "rows": [list(row) for row in result.fetchall()],
            },
        }
    except Exception as error:
        return {"ok": False, "error": f"Could not sample table '{name}': {error}"}
    finally:
        connection.close()


def run_sql(query):
    ok, cleaned_query = validate_sql(query)
    if not ok:
        return {"ok": False, "error": cleaned_query}

    connection = get_connection()
    timer = threading.Timer(10, connection.interrupt)
    try:
        timer.start()
        result = connection.execute(cleaned_query)
        return {
            "ok": True,
            "data": {
                "columns": [column[0] for column in result.description],
                "rows": [list(row) for row in result.fetchall()],
            },
        }
    except Exception as error:
        return {"ok": False, "error": f"SQL execution failed: {error}"}
    finally:
        timer.cancel()
        connection.close()
