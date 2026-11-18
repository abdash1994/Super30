"""Seed an orders table and measure a query before and after an index.

Uses SQLite from the standard library so the lab runs anywhere with no
database server. SQLite's version of EXPLAIN ANALYZE is EXPLAIN QUERY PLAN
(how the query will run); the amount of work is measured by counting
SQLite virtual-machine steps with a progress handler, which is
deterministic, unlike wall-clock time on a shared CI machine.
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

STATUSES = ("paid", "pending", "refunded", "failed")
START = date(2026, 1, 1)
STEP_GRANULARITY = 10  # count one tick per 10 VM instructions


def seed(conn: sqlite3.Connection, rows: int = 50_000, customers: int = 5_000,
         seed_value: int = 16) -> None:
    """Create `orders` and fill it with reproducible fake rows."""
    if rows < 1 or customers < 1:
        raise ValueError("rows and customers must be at least 1")
    rng = random.Random(seed_value)
    conn.execute("DROP TABLE IF EXISTS orders")
    conn.execute(
        "CREATE TABLE orders ("
        " id INTEGER PRIMARY KEY,"
        " customer_id INTEGER NOT NULL,"
        " status TEXT NOT NULL,"
        " created_at TEXT NOT NULL,"
        " amount_inr REAL NOT NULL)"
    )
    data = (
        (
            i,
            rng.randint(1, customers),
            rng.choice(STATUSES),
            (START + timedelta(days=rng.randint(0, 299))).isoformat(),
            round(rng.uniform(50, 5000), 2),
        )
        for i in range(1, rows + 1)
    )
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", data)
    conn.commit()


def query_plan(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[str]:
    """Return the 'detail' column of EXPLAIN QUERY PLAN, one string per step."""
    return [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params)]


def is_full_scan(plan: list[str]) -> bool:
    """True when any step reads a whole table or a whole index.

    SQLite says SCAN for "read everything" and SEARCH for "jump to the
    matching rows". "SCAN orders USING COVERING INDEX ..." is still a full
    scan: it reads every entry of the index instead of every row.
    """
    return any(step.startswith("SCAN") for step in plan)


def work_units(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> tuple[int, int]:
    """Run the query; return (work units, rows returned).

    One work unit = STEP_GRANULARITY SQLite VM instructions.
    """
    ticks = 0

    def tick() -> int:
        nonlocal ticks
        ticks += 1
        return 0  # 0 means "keep going"

    conn.set_progress_handler(tick, STEP_GRANULARITY)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.set_progress_handler(None, STEP_GRANULARITY)
    return ticks, len(rows)


@dataclass
class Measurement:
    label: str
    plan: list[str]
    full_scan: bool
    work: int
    rows: int


def measure(conn: sqlite3.Connection, label: str, sql: str,
            params: tuple = ()) -> Measurement:
    plan = query_plan(conn, sql, params)
    work, rows = work_units(conn, sql, params)
    return Measurement(label, plan, is_full_scan(plan), work, rows)


def insert_work(conn: sqlite3.Connection, n: int = 1_000, start_id: int = 10_000_000) -> int:
    """Work units to insert n rows: the write cost every index adds."""
    rng = random.Random(99)
    ticks = 0

    def tick() -> int:
        nonlocal ticks
        ticks += 1
        return 0

    conn.set_progress_handler(tick, STEP_GRANULARITY)
    try:
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
            (
                (start_id + i, rng.randint(1, 5000), "paid",
                 (START + timedelta(days=rng.randint(0, 299))).isoformat(), 100.0)
                for i in range(n)
            ),
        )
    finally:
        conn.set_progress_handler(None, STEP_GRANULARITY)
    conn.rollback()
    return ticks


BY_CUSTOMER = "SELECT id, amount_inr FROM orders WHERE customer_id = ?"
BY_DAY_FUNCTION = "SELECT id FROM orders WHERE date(created_at) = ?"
BY_DAY_RANGE = "SELECT id FROM orders WHERE created_at >= ? AND created_at < ?"
