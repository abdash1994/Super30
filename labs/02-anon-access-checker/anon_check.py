"""Anonymous-access checker.

Asks a Supabase/PostgREST project, using only its public (anon) key, which
tables it will hand rows back for. Run it against your own throwaway project.

Usage:
    export SUPABASE_URL=https://<project>.supabase.co
    export SUPABASE_ANON_KEY=<public anon key>
    python anon_check.py profiles orders invoices

Exit code is 1 if any table is EXPOSED, so it can gate a CI pipeline.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import requests

EXPOSED = "EXPOSED"  # anon key got real rows back
NO_ROWS = "NO_ROWS_VISIBLE"  # request allowed, zero rows (RLS filtered them, or the table is empty)
BLOCKED = "BLOCKED"  # 401/403: anon role has no grant on the table
NOT_FOUND = "NOT_FOUND"  # 404: no such table exposed through the API
ERROR = "ERROR"  # anything else, including network failures


@dataclass
class TableResult:
    table: str
    verdict: str
    status_code: int | None
    rows_seen: int
    detail: str = ""


def check_table(session, base_url: str, anon_key: str, table: str, timeout: float = 10.0) -> TableResult:
    """Try to read one row from `table` with the anon key and classify the answer."""
    url = f"{base_url.rstrip('/')}/rest/v1/{table}"
    headers = {"apikey": anon_key, "Authorization": f"Bearer {anon_key}"}
    try:
        response = session.get(url, headers=headers, params={"select": "*", "limit": "1"}, timeout=timeout)
    except requests.RequestException as exc:
        return TableResult(table, ERROR, None, 0, f"request failed: {type(exc).__name__}")

    code = response.status_code
    if code == 200:
        try:
            body = response.json()
        except ValueError:
            return TableResult(table, ERROR, code, 0, "200 but body was not JSON")
        rows = len(body) if isinstance(body, list) else 0
        return TableResult(table, EXPOSED if rows else NO_ROWS, code, rows)
    if code in (401, 403):
        return TableResult(table, BLOCKED, code, 0)
    if code == 404:
        return TableResult(table, NOT_FOUND, code, 0)
    return TableResult(table, ERROR, code, 0, f"unexpected status {code}")


def check_tables(session, base_url: str, anon_key: str, tables: list[str]) -> list[TableResult]:
    return [check_table(session, base_url, anon_key, t) for t in tables]


def format_report(results: list[TableResult]) -> str:
    """Plain-text table. Never includes the key."""
    lines = [f"{'table':<20} {'verdict':<16} {'status':<6} rows", "-" * 50]
    for r in results:
        status = "-" if r.status_code is None else str(r.status_code)
        line = f"{r.table:<20} {r.verdict:<16} {status:<6} {r.rows_seen}"
        if r.detail:
            line += f"  ({r.detail})"
        lines.append(line)
    exposed = sum(r.verdict == EXPOSED for r in results)
    lines.append("-" * 50)
    lines.append(f"{exposed} of {len(results)} tables exposed to the anon key")
    return "\n".join(lines)


def main(argv: list[str], env: dict | None = None, session=None) -> int:
    env = os.environ if env is None else env
    base_url = env.get("SUPABASE_URL")
    anon_key = env.get("SUPABASE_ANON_KEY")
    if not base_url or not anon_key or not argv:
        print("usage: SUPABASE_URL=... SUPABASE_ANON_KEY=... python anon_check.py <table> [<table> ...]", file=sys.stderr)
        return 2
    session = session or requests.Session()
    results = check_tables(session, base_url, anon_key, argv)
    print(format_report(results))
    return 1 if any(r.verdict == EXPOSED for r in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
