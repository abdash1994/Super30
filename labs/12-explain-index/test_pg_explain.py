"""PostgreSQL EXPLAIN ANALYZE output is a fixed text format, so no server is
needed to test the reader. These samples have the real shape of Postgres
output; the timings in them are made up for the test, not measured."""

import pytest

from pg_explain import speedup, summarise

BEFORE = """
Seq Scan on orders  (cost=0.00..1043.00 rows=10 width=12) (actual time=0.015..6.120 rows=7 loops=1)
  Filter: (customer_id = 42)
  Rows Removed by Filter: 49993
Planning Time: 0.080 ms
Execution Time: 6.150 ms
"""

AFTER = """
Index Scan using idx_orders_customer on orders  (cost=0.29..8.45 rows=10 width=12) (actual time=0.020..0.031 rows=7 loops=1)
  Index Cond: (customer_id = 42)
Planning Time: 0.110 ms
Execution Time: 0.050 ms
"""

BITMAP = """
Bitmap Heap Scan on orders  (cost=4.36..39.48 rows=10 width=12) (actual time=0.03..0.05 rows=7 loops=1)
  Recheck Cond: (customer_id = 42)
  ->  Bitmap Index Scan on idx_orders_customer  (cost=0.00..4.36 rows=10 width=0) (actual time=0.02..0.02 rows=7 loops=1)
        Index Cond: (customer_id = 42)
Execution Time: 0.070 ms
"""


def test_reads_seq_scan():
    s = summarise(BEFORE)
    assert s.top_node == "Seq Scan"
    assert s.is_seq_scan
    assert s.execution_ms == pytest.approx(6.15)
    assert s.rows_removed_by_filter == 49993


def test_reads_index_scan():
    s = summarise(AFTER)
    assert s.top_node == "Index Scan"
    assert not s.is_seq_scan
    assert s.rows_removed_by_filter == 0


def test_top_node_is_the_first_line_not_the_child():
    assert summarise(BITMAP).top_node == "Bitmap Heap Scan"


def test_speedup():
    assert speedup(summarise(BEFORE), summarise(AFTER)) == pytest.approx(123.0)


@pytest.mark.parametrize("text", ["", "Seq Scan on orders  (cost=0.00..1.00 rows=1 width=4)"])
def test_rejects_text_that_is_not_explain_analyze(text):
    with pytest.raises(ValueError):
        summarise(text)
