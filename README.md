# text-to-sql-agent

A natural-language to SQL analytics agent. A user asks a business question in English, the agent inspects the database schema, writes SQL, executes it, self-corrects on errors, and returns the answer along with the SQL used.

## Planned Features

- Tool-calling agent loop
- Schema grounding
- Error recovery
- Read-only guardrails with query limits and timeouts
- An evaluation harness reporting execution accuracy on 50+ questions

## Planned Tech Stack

- Python
- DuckDB, later AWS Athena
- An LLM API with tool calling
- sqlglot
- Streamlit

## Status

In progress, setup stage.

## Architecture

Placeholder for the system architecture and component responsibilities.

## Results

Placeholder for the evaluation accuracy table.

| Metric | Result |
| --- | --- |
| Execution accuracy | TBD |

## How to Run

Placeholder for local setup and execution instructions.
