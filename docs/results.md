# Evaluation Results

| Config | Execution accuracy | Ambiguous | Avg. LLM calls/question | Avg. seconds/question | Failures | Routing fractions |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| v1 | 3/5 (60.0%) | n/a | 3.00 | 3.68 | 2 | n/a |
| v2 | 2/5 (40.0%) | n/a | 3.00 | 8.43 | 3 | n/a |
| v3 | 3/5 (60.0%) | n/a | 3.60 | 12.39 | 2 | n/a |
| v5 smoke (LLM unavailable) | n/a | 0 | 2.00 | 17.41 | 5 connection failures | complex 100% (fallback) |

The v5 smoke attempt could not reach the configured LLM endpoint. Its accuracy is not a meaningful SQL quality score; all five questions fell back to the full pipeline after planner connection failures.
