import sqlite3

import pytest

from demo import evaluate, fake_llm_for, report
from eval_cases import CASES
from text_to_sql import (
    ALLOWED_TABLES,
    Rejected,
    ask,
    build_prompt,
    extract_sql,
    open_read_only,
    run_query,
    seed,
    validate_sql,
)


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return seed(tmp_path_factory.mktemp("lab14") / "shop.db")


def always(sql):
    return lambda prompt: sql


# --- prompt and extraction ----------------------------------------------------

def test_prompt_shows_allowed_tables_only():
    prompt = build_prompt("How many customers?")
    assert "customers(" in prompt and "orders(" in prompt
    assert "staff_salaries" not in prompt
    assert prompt.endswith("Question: How many customers?\nSQL:")


@pytest.mark.parametrize("answer", [
    "SELECT 1", "```sql\nSELECT 1\n```", "Here you go:\n```\nSELECT 1\n```\nThanks", "  SELECT 1\n",
])
def test_extract_sql_handles_fences_and_chatter(answer):
    assert extract_sql(answer) == "SELECT 1"


# --- guard 1: validator -------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM orders;",
    "with x as (select 1) select * from x",
    "SELECT * FROM orders WHERE status = 'drop; delete'",  # keywords inside a string are data
    "SELECT created_at, updated FROM orders",  # 'created_at' is not CREATE
    "SELECT 1 -- ; DROP TABLE orders",  # a comment is not a second statement
])
def test_validator_allows_reads(sql):
    assert validate_sql(sql).lower().startswith(("select", "with"))


@pytest.mark.parametrize("sql, reason", [
    ("DELETE FROM orders", "only SELECT"),
    ("drop table orders", "only SELECT"),
    ("UPDATE orders SET amount_inr = 0", "only SELECT"),
    ("PRAGMA table_info(orders)", "only SELECT"),
    ("ATTACH 'other.db' AS o", "only SELECT"),
    ("SELECT 1; DROP TABLE orders", "more than one statement"),
    ("WITH x AS (SELECT 1) DELETE FROM orders", "forbidden keyword: DELETE"),
    ("WITH x AS (SELECT 1) INSERT INTO orders SELECT * FROM x", "forbidden keyword: INSERT"),
    ("   ", "empty"),
])
def test_validator_rejects_with_a_reason(sql, reason):
    with pytest.raises(Rejected, match=reason):
        validate_sql(sql)


# --- guard 2: read-only user --------------------------------------------------

def test_mode_ro_alone_refuses_writes(db):
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("DELETE FROM orders")
    conn.close()


@pytest.mark.parametrize("sql", [
    "DELETE FROM orders",
    "DROP TABLE orders",
    "INSERT INTO orders (id) VALUES (999999)",
    "CREATE TABLE t (x)",
    "PRAGMA query_only = OFF",
    "SELECT * FROM staff_salaries",
    "SELECT name FROM sqlite_master",
])
def test_read_only_user_blocks_without_the_validator(db, sql):
    conn = open_read_only(db)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(sql).fetchall()
    conn.close()


def test_read_only_user_still_reads_allowed_tables(db):
    conn = open_read_only(db)
    assert conn.execute("SELECT COUNT(*) FROM customers").fetchone() == (200,)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone() == (2000,)
    conn.close()
    assert ALLOWED_TABLES == {"customers", "orders"}


def test_nothing_was_changed_by_the_attempts(db):
    for case in CASES:
        ask(case["question"], fake_llm_for(CASES), db, validate=False)
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"customers", "orders", "staff_salaries"}
    assert conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'refunded'").fetchone()[0] > 0
    conn.close()


# --- guard 3: work budget and row cap -------------------------------------------

def test_work_budget_stops_a_runaway_join(db):
    answer = ask("x", always("SELECT COUNT(*) FROM orders a, orders b, orders c"), db)
    assert (answer.status, answer.stopped_by) == ("blocked", "work_budget")


def test_row_cap_truncates_and_says_so(db):
    conn = open_read_only(db)
    columns, rows, truncated = run_query(conn, "SELECT id FROM orders", max_rows=10)
    conn.close()
    assert columns == ["id"] and len(rows) == 10 and truncated


def test_a_plain_sql_error_is_an_error_not_a_block(db):
    answer = ask("x", always("SELECT no_such_column FROM orders"), db)
    assert answer.status == "error" and answer.stopped_by is None


# --- the 12-question eval: pins the README numbers ------------------------------

def test_eval_scorecard_matches_readme(db):
    card = evaluate(db)
    assert (card.correct, card.wrong, card.false_blocks) == (6, 1, 0)
    assert (card.blocked, card.missed) == (5, 0)
    assert card.stopped_by == {"validator": 3, "read_only_user": 1, "work_budget": 1}
    assert "q07 | How many orders were above 5,000 rupees? | wrong: got [(1030,)], expected [(1017,)]" in report(card)


def test_every_dangerous_answer_is_still_stopped_with_the_validator_off(db):
    card = evaluate(db, validate=False)
    assert (card.blocked, card.missed) == (5, 0)
    assert card.stopped_by == {"read_only_user": 3, "driver": 1, "work_budget": 1}
