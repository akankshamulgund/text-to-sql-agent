from pathlib import Path

from app import bootstrap


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_builds_database_only_when_missing(monkeypatch, tmp_path):
    database_path = tmp_path / "analytics.duckdb"
    calls = []
    monkeypatch.setattr(bootstrap, "DATABASE_PATH", database_path)
    monkeypatch.setattr(bootstrap, "build_database", lambda path: calls.append(path))

    bootstrap.ensure_database()
    database_path.touch()
    bootstrap.ensure_database()

    assert calls == [database_path]


def test_readme_documents_available_commands():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    for command in (
        "python.exe data/load_data.py",
        "-m streamlit run app/main.py",
        "-m pytest",
        "-m eval.run_eval --config v1",
        "-m eval.compare",
    ):
        assert command in readme

    for path in ("app/main.py", "data/load_data.py", "eval/run_eval.py"):
        assert (PROJECT_ROOT / path).exists()
