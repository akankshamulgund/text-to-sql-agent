# Evaluation Failure Analysis

This analysis uses the seven failed records across the result files currently in `eval/results` (`v1`, `v2`, and `v3`). The benchmark has five public TPC-H questions per configuration.

| Failure type | Count |
| --- | ---: |
| Wrong join | 1 |
| Wrong filter | 0 |
| Wrong column or output shape | 3 |
| Ambiguous question | 0 |
| Timeout | 0 |
| Other | 3 |

## Wrong join (1)

**Question:** Which supplier supplies the most distinct parts? (v3)

**Wrong SQL:** `SELECT supplier.s_suppkey, COUNT(DISTINCT partsupp.ps_partkey) AS distinct_parts FROM supplier LEFT JOIN partsupp ON supplier.s_suppkey = partsupp.ps_suppkey GROUP BY supplier.s_suppkey ORDER BY distinct_parts DESC LIMIT 1`

**Correct SQL:** `SELECT s.s_suppkey, s.s_name, COUNT(DISTINCT ps.ps_partkey) AS distinct_parts FROM supplier s JOIN partsupp ps ON s.s_suppkey = ps.ps_suppkey GROUP BY s.s_suppkey, s.s_name ORDER BY distinct_parts DESC, s.s_suppkey LIMIT 1`

The query used a `LEFT JOIN` and did not return the supplier name or apply the deterministic tie-break. A validator check for requested identity columns and stable ordering after aggregate rankings would help.

## Wrong filter (0)

No recorded failure was a wrong-filter error. The 1995 monthly query used a valid year condition; its mismatch was the returned column shape.

## Wrong column or output shape (3)

**Question:** Which 5 customers have the highest total order value? (v1 and v2)

**Wrong SQL:** `SELECT c.c_custkey, c.c_name, SUM(o.o_totalprice) AS total_order_value FROM customer c JOIN orders o ON c.c_custkey = o.o_custkey GROUP BY c.c_custkey, c.c_name ORDER BY total_order_value DESC LIMIT 5`

**Correct SQL:** `SELECT c.c_name, SUM(o.o_totalprice) AS total_order_value FROM customer c JOIN orders o ON c.c_custkey = o.o_custkey GROUP BY c.c_name ORDER BY total_order_value DESC LIMIT 5`

**Question:** Show monthly order counts for 1995 (v2)

**Wrong SQL:** `SELECT EXTRACT(YEAR FROM o_orderdate) AS yr, EXTRACT(MONTH FROM o_orderdate) AS mon, COUNT(*) AS order_count FROM orders WHERE EXTRACT(YEAR FROM o_orderdate) = 1995 GROUP BY yr, mon ORDER BY mon`

**Correct SQL:** `SELECT DATE_TRUNC('month', o_orderdate)::DATE AS month, COUNT(*) AS order_count FROM orders WHERE o_orderdate >= DATE '1995-01-01' AND o_orderdate < DATE '1996-01-01' GROUP BY 1 ORDER BY 1`

These queries were close logically but returned extra columns or a different month representation. The evaluator compares rows and columns, so the validator should compare the final projection directly with the wording of the question.

## Ambiguous question (0)

No evaluation record was routed as ambiguous. The planner requests clarification when a required metric, time range, or ranking rule has no sensible default.

## Timeout (0)

No recorded failure was a database timeout. Query execution has a 10-second interrupt guard.

## Other (3)

**Question:** Which supplier supplies the most distinct parts? (v1 and v2)

**Wrong SQL:** `SELECT supplier.s_name, COUNT(DISTINCT partsupp.ps_partkey) AS distinct_parts FROM partsupp JOIN supplier ON partsupp.ps_suppkey = supplier.s_suppkey GROUP BY supplier.s_name ORDER BY distinct_parts DESC LIMIT 1`

**Correct SQL:** `SELECT s.s_suppkey, s.s_name, COUNT(DISTINCT ps.ps_partkey) AS distinct_parts FROM supplier s JOIN partsupp ps ON s.s_suppkey = ps.ps_suppkey GROUP BY s.s_suppkey, s.s_name ORDER BY distinct_parts DESC, s.s_suppkey LIMIT 1`

**Question:** Show monthly order counts for 1995 (v3)

**Wrong SQL:** No SQL was produced; the SQL agent returned HTTP 400.

**Correct SQL:** `SELECT DATE_TRUNC('month', o_orderdate)::DATE AS month, COUNT(*) AS order_count FROM orders WHERE o_orderdate >= DATE '1995-01-01' AND o_orderdate < DATE '1996-01-01' GROUP BY 1 ORDER BY 1`

Two supplier failures omitted the tie-break for suppliers tied at the maximum count. The remaining failure was an upstream agent request error. Deterministic ranking validation and retry telemetry for provider errors would address these cases.
