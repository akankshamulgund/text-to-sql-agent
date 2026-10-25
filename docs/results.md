# Evaluation Results

| Config | Execution accuracy | Ambiguous | Avg. LLM calls/question | Avg. seconds/question | Failures | Routing fractions |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| v1 | 3/5 (60.0%) | n/a | 3.00 | 3.68 | 2 | n/a |
| v2 | 2/5 (40.0%) | n/a | 3.00 | 8.43 | 3 | n/a |
| v3 | 3/5 (60.0%) | n/a | 3.60 | 12.39 | 2 | n/a |
| v5 (5-question smoke) | 4/5 (80.0%) | 0 | 7.20 | 23.08 | 1 | complex 80%, simple 20% |

The v5 result is a five-question smoke run. One hard question returned a result that did not match its expected rows.
