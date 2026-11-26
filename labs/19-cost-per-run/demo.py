"""Run the automation a few ways and print cost per run from the log."""

from __future__ import annotations

import itertools
import tempfile
from decimal import Decimal
from pathlib import Path

from automation import FakeLLM, run_triage
from cost_log import RunLogger, summarise

BASE = [
    "I was charged twice for my plan this month, invoice 4471. Please refund the extra payment. "
    "I have attached the bank statement and the receipt from the checkout page for both charges.",
    "The export button does nothing on Safari. I click it, the spinner shows for a second and then "
    "nothing downloads. Chrome works fine. This blocks our month-end report for the finance team.",
    "Congratulations! You win a prize. Click this link to claim your reward before midnight.",
    "The dashboard shows yesterday's numbers even after I refresh. Our sales team relies on it every "
    "morning, so stale numbers mean they call the wrong customers first. Started after Tuesday.",
]


def tickets(n: int) -> list[str]:
    return list(itertools.islice(itertools.cycle(BASE), n))


def fixed_clock():
    counter = itertools.count()
    return lambda: f"2026-11-26T09:00:{next(counter) % 60:02d}+00:00"


def run(log: Path, run_id: str, n: int, budget: str | None = None, reply_model: str = "large"):
    with RunLogger(log, budget_usd=Decimal(budget) if budget else None,
                   run_id=run_id, clock=fixed_clock()) as logger:
        run_triage(tickets(n), FakeLLM(), logger, reply_model=reply_model)
    return logger


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "runs.jsonl"
        rows = [
            ("quiet day, 20 tickets", run(log, "quiet", 20)),
            ("busy day, 200 tickets", run(log, "busy", 200)),
            ("busy day, $0.25 budget", run(log, "capped", 200, budget="0.25")),
            ("20 tickets, replies on small", run(log, "all-small", 20, reply_model="small")),
        ]
        print("| Run | Status | Tickets done | Calls | Cost | Cost per ticket |")
        print("| --- | --- | --- | --- | --- | --- |")
        for name, lg in rows:
            per = lg.total_usd / lg.items if lg.items else Decimal(0)
            print(f"| {name} | {lg.status} | {lg.items} | {lg.calls} | ${lg.total_usd:.4f} | ${per:.5f} |")
        s = summarise(log)
        print()
        for step, cost in sorted(s["by_step"].items(), key=lambda kv: kv[1], reverse=True):
            print(f"{step}: ${cost:.4f} ({cost / s['total'] * 100:.0f}% of all spend)")


if __name__ == "__main__":
    main()
