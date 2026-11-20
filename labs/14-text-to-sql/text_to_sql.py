"""Plain English to SQL, with three guards between the model and the data.

The flow:

1. ``build_prompt(question)`` puts the allowed schema and the rules in front of
   the model.
2. ``llm(prompt)`` returns text. It is any function ``prompt -> text``: a real
   model client in production, a fake in the tests. Nothing here touches the
   network.
3. ``extract_sql`` pulls the SQL out of the answer (models like code fences).
4. Three guards, each able to stop a bad query on its own:

   - **validator** (``validate_sql``): one statement, starts with SELECT or
     WITH, no write or admin keywords. Cheap, runs before the database is
     touched, gives a clear reason.
   - **read-only user** (``open_read_only``): the file is opened with
     ``mode=ro`` and ``PRAGMA query_only``, and an authorizer allows only
     reads of allowlisted tables. Even SQL that fools the validator cannot
     write or read ``staff_salaries``.
   - **work budget**: a progress handler aborts any query that runs more than
     ``max_steps`` VM instructions, and at most ``max_rows`` rows come back.

``ask(question, llm, db_path)`` runs the whole flow and returns an ``Answer``
saying what happened and which guard (if any) stopped it.
"""

from __future__ import annotations

import random
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ALLOWED_TABLES = frozenset({"customers", "orders"})

SCHEMA_FOR_PROMPT = """\
customers(id INTEGER PRIMARY KEY, name TEXT, city TEXT, signup_date TEXT 'YYYY-MM-DD')
orders(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
       amount_inr INTEGER, status TEXT 'paid'|'refunded', created_at TEXT 'YYYY-MM-DD')"""

PROMPT_TEMPLATE = """\
You write one SQLite SELECT query that answers the question.
Use only these tables:
{schema}
Rules: one statement, SELECT only, no explanations. Reply with the SQL only.

Question: {question}
SQL:"""

FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create",
    "attach", "detach", "pragma", "vacuum", "reindex", "truncate", "grant",
)

CITIES = ("Mumbai", "Delhi", "Bengaluru", "Pune", "Kolkata")


class Rejected(ValueError):
    """The validator refused the SQL before it reached the database."""


@dataclass
class Answer:
    question: str
    sql: str
    status: str  # "ok", "blocked" or "error"
    stopped_by: str | None = None  # "validator", "read_only_user", "work_budget", "driver"
    reason: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    truncated: bool = False


# --- the prompt and the model's answer ------------------------------------

def build_prompt(question: str) -> str:
    return PROMPT_TEMPLATE.format(schema=SCHEMA_FOR_PROMPT, question=question.strip())


_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_sql(answer: str) -> str:
    """Take the SQL out of a model answer: fenced block if any, else the text."""
    match = _FENCE.search(answer)
    sql = match.group(1) if match else answer
    return sql.strip()


# --- guard 1: the validator -------------------------------------------------

_STRING_OR_COMMENT = re.compile(
    r"'(?:[^']|'')*'"      # 'single quoted', with '' escapes
    r'|"(?:[^"]|"")*"'     # "quoted identifier"
    r"|--[^\n]*"           # -- line comment
    r"|/\*.*?\*/",         # /* block comment */
    re.DOTALL,
)


def _code_only(sql: str) -> str:
    """Blank out strings and comments so keywords inside them don't count."""
    return _STRING_OR_COMMENT.sub(" ", sql)


def validate_sql(sql: str) -> str:
    """Return the SQL (without a trailing semicolon) or raise ``Rejected``."""
    code = _code_only(sql).strip()
    if not code:
        raise Rejected("empty query")
    code = code.rstrip(";").strip()
    if ";" in code:
        raise Rejected("more than one statement")
    first = code.split(None, 1)[0].lower()
    if first not in ("select", "with"):
        raise Rejected(f"only SELECT is allowed, got {first.upper()}")
    words = set(re.findall(r"[a-z_]+", code.lower()))
    bad = sorted(words.intersection(FORBIDDEN_KEYWORDS))
    if bad:
        raise Rejected(f"forbidden keyword: {', '.join(k.upper() for k in bad)}")
    return sql.strip().rstrip(";").strip()


# --- guard 2: the read-only user -------------------------------------------

def _authorizer(allowed_tables: frozenset[str]) -> Callable:
    def check(action, arg1, arg2, db_name, trigger):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if arg1 in allowed_tables else sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_OK
        if action == getattr(sqlite3, "SQLITE_RECURSIVE", -1):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return check


def open_read_only(db_path: Path, allowed_tables: frozenset[str] = ALLOWED_TABLES) -> sqlite3.Connection:
    """Connect the way an analyst-bot user should: can read some tables, nothing else.

    In Postgres the same idea is a role with ``GRANT SELECT`` on chosen tables
    only and ``default_transaction_read_only = on`` (see ``readonly_role.sql``).
    """
    conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(_authorizer(allowed_tables))
    return conn


# --- the whole flow ------------------------------------------------------------

def run_query(conn: sqlite3.Connection, sql: str, max_rows: int = 100, max_steps: int = 2_000_000):
    """Run SQL under the work budget. Returns (columns, rows, truncated)."""
    counter = {"ticks": 0}
    every = 1_000

    def budget():
        counter["ticks"] += 1
        return 1 if counter["ticks"] * every > max_steps else 0

    conn.set_progress_handler(budget, every)
    try:
        cur = conn.execute(sql)
        rows = cur.fetchmany(max_rows + 1)
    finally:
        conn.set_progress_handler(None, every)
    columns = [d[0] for d in cur.description or []]
    truncated = len(rows) > max_rows
    return columns, [tuple(r) for r in rows[:max_rows]], truncated


def _classify(err: sqlite3.Error) -> str:
    text = str(err).lower()
    if "interrupted" in text:
        return "work_budget"
    if "not authorized" in text or "prohibited" in text or "readonly" in text:
        return "read_only_user"
    if "one statement at a time" in text:
        # Python's execute() refuses stacked statements; executescript() would run them.
        return "driver"
    return ""


def ask(
    question: str,
    llm: Callable[[str], str],
    db_path: Path,
    *,
    validate: bool = True,
    max_rows: int = 100,
    max_steps: int = 2_000_000,
) -> Answer:
    sql = extract_sql(llm(build_prompt(question)))
    if validate:
        try:
            sql = validate_sql(sql)
        except Rejected as err:
            return Answer(question, sql, "blocked", "validator", str(err))
    conn = open_read_only(db_path)
    try:
        columns, rows, truncated = run_query(conn, sql, max_rows=max_rows, max_steps=max_steps)
    except sqlite3.Error as err:
        layer = _classify(err)
        if layer:
            return Answer(question, sql, "blocked", layer, str(err))
        return Answer(question, sql, "error", None, str(err))
    finally:
        conn.close()
    return Answer(question, sql, "ok", columns=columns, rows=rows, truncated=truncated)


# --- demo data -------------------------------------------------------------------

def seed(db_path: Path, customers: int = 200, orders: int = 2_000, seed_value: int = 14) -> Path:
    """Create a small shop database. Same seed, same data, every run."""
    rng = random.Random(seed_value)
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    with conn:
        conn.executescript(
            """
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT, signup_date TEXT);
            CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
                                 amount_inr INTEGER, status TEXT, created_at TEXT);
            CREATE TABLE staff_salaries (staff_id INTEGER PRIMARY KEY, name TEXT, salary_inr INTEGER);
            """
        )
        conn.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?)",
            [
                (i, f"Customer {i}", rng.choice(CITIES), f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}")
                for i in range(1, customers + 1)
            ],
        )
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
            [
                (
                    i,
                    rng.randint(1, customers),
                    rng.randrange(200, 10_001, 50),
                    "refunded" if rng.random() < 0.08 else "paid",
                    f"2026-{rng.randint(1, 6):02d}-{rng.randint(1, 28):02d}",
                )
                for i in range(1, orders + 1)
            ],
        )
        conn.executemany(
            "INSERT INTO staff_salaries VALUES (?, ?, ?)",
            [(i, f"Staff {i}", rng.randrange(600_000, 3_000_001, 10_000)) for i in range(1, 21)],
        )
    conn.close()
    return db_path
