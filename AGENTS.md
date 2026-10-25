# text-to-sql-agent

## Project structure

- `app/`: Streamlit dashboard, charts, queries, and pinned tiles.
- `agents/`: Planner, schema, SQL, validator, insight, and visualization agents.
- `tools/`: DuckDB connection and read-only query helpers.
- `guardrails/`: SQL safety checks.
- `data/`: Local TPC-H sample database generator. Generated `.duckdb` files are local only.
- `eval/`: Question set, evaluation runner, and recorded result files.
- `tests/`: Pytest suite.
- `docs/`: Project documentation and evaluation summaries.

## Running locally

Use the repository virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe data/load_data.py
.\.venv\Scripts\python.exe -m streamlit run app/main.py
```

Run evaluations with:

```powershell
.\.venv\Scripts\python.exe -m eval.run_eval --config v0
.\.venv\Scripts\python.exe -m eval.run_eval --config v5 --limit 5 --delay 0
.\.venv\Scripts\python.exe -m eval.compare
```

## Rules

- Never print, log, or commit API keys.
- Never commit `.env`, `.duckdb`, or Streamlit secrets files.
- Keep code simple and add comments where they clarify non-obvious behavior.
