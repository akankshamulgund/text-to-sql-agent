import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "results.md"


def render_comparison():
    rows = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        accuracy = data.get("accuracy_overall", {})
        rows.append(
            "| {config} | {correct}/{total} ({accuracy:.1%}) | {calls:.2f} | {seconds:.2f} | {failures} |".format(
                config=data.get("config", path.stem),
                correct=accuracy.get("correct", 0),
                total=accuracy.get("total", 0),
                accuracy=accuracy.get("accuracy", 0.0),
                calls=data.get("average_llm_calls_per_question", 0.0),
                seconds=data.get("average_seconds_per_question", 0.0),
                failures=sum(data.get("failure_categories", {}).values()),
            )
        )
    table = [
        "# Evaluation Results",
        "",
        "| Config | Execution accuracy | Avg. LLM calls/question | Avg. seconds/question | Failures |",
        "| --- | ---: | ---: | ---: | ---: |",
        *(rows or ["| No results yet | - | - | - | - |"]),
        "",
    ]
    return "\n".join(table)


def main():
    markdown = render_comparison()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
