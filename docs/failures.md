# Smoke-Test Failure Analysis

The v1/v2/v3 comparison used the same five questions and model (`openai/gpt-oss-20b`). It is a small smoke set, not a general accuracy estimate.

| Config | Accurate | Avg. LLM calls/question | Avg. seconds/question |
| --- | ---: | ---: | ---: |
| v1 (schema, no validator) | 3/5 (60%) | 3.00 | 3.68 |
| v2 (no schema, validator) | 2/5 (40%) | 3.00 | 8.43 |
| v3 (schema and validator) | 3/5 (60%) | 3.60 | 12.39 |

## Failed Questions

### v1

- **Top five customers:** The computed top five and totals were right, but generated SQL included `c_custkey` while the gold projection contains only customer name and total value. The evaluator compares result shape strictly, so this is an execution mismatch rather than a wrong ranking.
- **Supplier with most distinct parts:** The query sorted by count only. Many suppliers tie at 80 parts; the gold SQL breaks ties by ascending `s_suppkey`, while the generated query returned supplier 373. Local DuckDB results confirm suppliers 1 through 12 already share the maximum count of 80.

### v2

- **Top five customers:** Same projection mismatch as v1: it returned the extra customer key, though the ranking and totals matched.
- **Monthly 1995 orders:** The query grouped by separate `yr` and `mon` columns instead of a single month column. The year filter and monthly counts were conceptually aligned, but the output schema differed from gold.
- **Supplier with most distinct parts:** It returned supplier 551 with 80 parts. The gold tie-break selects the lowest supplier key; the generated query omitted that tie-break and did not return the identifying key.

### v3

- **Monthly 1995 orders:** The agent failed before producing SQL with HTTP 400, so this is an API/tool-loop failure, not a demonstrated SQL error. The saved trace had one schema call followed by the failed SQL-agent request; the provider response did not include a diagnostic body.
- **Supplier with most distinct parts:** The query used a LEFT JOIN, grouped only by supplier key, and ordered only by count. Because many suppliers tie at 80, it returned supplier 281 rather than applying the gold lowest-key tie-break. The join still returned the correct maximum count, but the selected supplier was nondeterministic relative to the benchmark.

## Interpretation

On this five-question set, the validator-only configuration (v2) did not improve accuracy over v1 and took substantially longer; average recorded model-call counts were equal at 3.0. Enabling both agents (v3) matched v1 accuracy, increased calls to 3.6/question, and had the highest latency. These small results do not establish that validation is ineffective generally; they show this validator did not reliably fix projection, output-shape, or deterministic tie-break issues in this run.
