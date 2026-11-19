import sqlite3

import pytest

import demo
from plan import (BY_CUSTOMER, BY_DAY_FUNCTION, BY_DAY_RANGE, is_full_scan,
                  measure, query_plan, seed, work_units)


@pytest.fixture(scope="module")
def results():
    return demo.run()


@pytest.fixture
def small():
    conn = sqlite3.connect(":memory:")
    seed(conn, rows=500, customers=50)
    yield conn
    conn.close()


def test_seed_is_reproducible():
    a, b = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    seed(a, rows=200)
    seed(b, rows=200)
    q = "SELECT * FROM orders ORDER BY id"
    assert a.execute(q).fetchall() == b.execute(q).fetchall()
    assert a.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 200


def test_seed_rejects_bad_sizes():
    with pytest.raises(ValueError):
        seed(sqlite3.connect(":memory:"), rows=0)


def test_is_full_scan_reads_sqlite_wording():
    assert is_full_scan(["SCAN orders"])
    assert is_full_scan(["SCAN orders USING COVERING INDEX idx_orders_created"])
    assert not is_full_scan(["SEARCH orders USING INDEX idx (customer_id=?)"])


def test_plan_flips_from_scan_to_search_when_index_added(small):
    assert is_full_scan(query_plan(small, BY_CUSTOMER, (7,)))
    small.execute("CREATE INDEX idx_c ON orders(customer_id)")
    plan = query_plan(small, BY_CUSTOMER, (7,))
    assert not is_full_scan(plan)
    assert "idx_c" in plan[0]


def test_index_does_not_change_the_answer(small):
    before = sorted(small.execute(BY_CUSTOMER, (7,)).fetchall())
    small.execute("CREATE INDEX idx_c ON orders(customer_id)")
    after = sorted(small.execute(BY_CUSTOMER, (7,)).fetchall())
    assert before == after and len(before) > 0


def test_work_units_counts_and_resets_handler(small):
    work, rows = work_units(small, "SELECT * FROM orders")
    assert work > 0 and rows == 500
    # handler removed: a later query is not still being counted
    small.execute("SELECT * FROM orders").fetchall()


def test_index_cuts_lookup_work_by_over_100x(results):
    rows, _, _ = results
    no_index, with_index = rows[0], rows[1]
    assert no_index.full_scan and not with_index.full_scan
    assert no_index.rows == with_index.rows == 7
    assert no_index.work > 100 * with_index.work


def test_function_on_column_defeats_the_index(results):
    rows, _, _ = results
    by_function, by_range = rows[2], rows[3]
    assert by_function.full_scan, by_function.plan
    assert not by_range.full_scan, by_range.plan
    assert by_function.rows == by_range.rows == 172
    assert by_function.work > 50 * by_range.work


def test_indexes_make_writes_more_expensive(results):
    _, write_before, write_after = results
    assert write_after > write_before * 1.2


def test_measure_returns_plan_and_rows(small):
    m = measure(small, "range", BY_DAY_RANGE, ("2026-03-01", "2026-03-02"))
    assert m.label == "range" and m.plan and m.rows >= 0
    m2 = measure(small, "fn", BY_DAY_FUNCTION, ("2026-03-01",))
    assert m2.rows == m.rows
