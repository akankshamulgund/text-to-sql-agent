# text-to-sql-agent

An AI analytics dashboard where users ask questions in English and a multi-agent system turns them into SQL, validates them, runs them, and returns charts and summaries that can be pinned to the dashboard.

## Agents

- **Planner/Router**: Breaks down the question and routes work to the right agents.
- **Schema**: Finds relevant tables, columns, and relationships.
- **SQL**: Generates SQL grounded in the available schema.
- **Validator/Critic**: Checks SQL for correctness, safety, and likely failure modes.
- **Insight**: Turns query results into concise business summaries.
- **Visualization**: Selects and prepares useful charts for the dashboard.

## Planned Features

- Multi-agent pipeline
- Self-correcting SQL
- Read-only guardrails
- Dashboard with KPI cards and pinnable tiles
- Agent trace panel
- Evaluation harness reporting execution accuracy

## Tech Stack

- Python
- Streamlit
- Plotly
- DuckDB, later AWS Athena
- sqlglot
- An LLM API with tool calling

## Status

In progress, setup stage.

## Architecture

Placeholder for the dashboard, agent pipeline, tools, guardrails, and data flow.

## Results

Placeholder for the evaluation accuracy table.

| Metric | Result |
| --- | --- |
| Execution accuracy | TBD |

## How to Run

Create the virtual environment, install the dependencies, and start the dashboard:

```bash
streamlit run app/main.py
```
