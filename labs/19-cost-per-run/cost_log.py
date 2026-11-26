"""Lab 19: log the cost of every model call, and the total for every run.

Each line of the log is one JSON object (JSONL), so the file can be appended
to safely, read line by line, and loaded into a spreadsheet or a database.

    {"type": "call", "run_id": ..., "step": "classify", "model": "small", "input_tokens": 92, ...}
    {"type": "run",  "run_id": ..., "status": "ok", "calls": 37, "cost_usd": "0.0412", ...}

Money uses Decimal (stored as a string in JSON) so totals never drift.
Prices are per 1 million tokens and are an input, never hard-coded in the logic.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

PER_MILLION = Decimal(1_000_000)

# Example prices in USD per 1M tokens. Assumptions for the lab, not quotes:
# check your provider's price page and pass your own table.
DEFAULT_PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "small": (Decimal("0.25"), Decimal("1.25")),
    "large": (Decimal("3"), Decimal("15")),
}


class BudgetExceeded(Exception):
    """Raised when a run's spend goes over its budget."""


class UnknownModel(KeyError):
    """Raised when a call uses a model with no price, so it cannot go unbilled."""


def call_cost(model: str, input_tokens: int, output_tokens: int,
              prices: dict[str, tuple[Decimal, Decimal]] = DEFAULT_PRICES) -> Decimal:
    if model not in prices:
        raise UnknownModel(f"no price for model {model!r}; add it to the price table")
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts cannot be negative")
    in_price, out_price = prices[model]
    return (Decimal(input_tokens) * in_price + Decimal(output_tokens) * out_price) / PER_MILLION


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RunLogger:
    """One logger per run. Use as a context manager so the run line is always written."""

    log_path: Path
    budget_usd: Decimal | None = None
    prices: dict[str, tuple[Decimal, Decimal]] = field(default_factory=lambda: dict(DEFAULT_PRICES))
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    clock: Callable[[], str] = _utc_now
    total_usd: Decimal = Decimal("0")
    calls: int = 0
    items: int = 0
    status: str = "running"

    def _write(self, record: dict) -> None:
        with Path(self.log_path).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def record(self, step: str, model: str, usage: dict) -> Decimal:
        """Log one model call from its usage numbers; stop the run if over budget."""
        input_tokens = int(usage["input_tokens"])
        output_tokens = int(usage["output_tokens"])
        cost = call_cost(model, input_tokens, output_tokens, self.prices)
        self.total_usd += cost
        self.calls += 1
        self._write({
            "type": "call", "run_id": self.run_id, "ts": self.clock(), "step": step,
            "model": model, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": str(cost),
        })
        if self.budget_usd is not None and self.total_usd > self.budget_usd:
            raise BudgetExceeded(f"run {self.run_id} spent ${self.total_usd} of ${self.budget_usd}")
        return cost

    def __enter__(self) -> "RunLogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.status = "ok"
        elif issubclass(exc_type, BudgetExceeded):
            self.status = "stopped_budget"
        else:
            self.status = "failed"
        per_item = (self.total_usd / self.items) if self.items else Decimal("0")
        self._write({
            "type": "run", "run_id": self.run_id, "ts": self.clock(), "status": self.status,
            "calls": self.calls, "items": self.items, "cost_usd": str(self.total_usd),
            "cost_per_item_usd": str(per_item.quantize(Decimal("0.000001"))),
        })
        # Swallow a budget stop (the run line already says why); let real errors through.
        return exc_type is not None and issubclass(exc_type, BudgetExceeded)


def read_log(log_path: Path) -> list[dict]:
    lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def summarise(log_path: Path) -> dict:
    """Cost per run and per step, rebuilt from call lines (so a crashed run still counts)."""
    runs: dict[str, dict] = {}
    by_step: dict[str, Decimal] = defaultdict(Decimal)
    for rec in read_log(log_path):
        run = runs.setdefault(rec["run_id"], {"cost": Decimal("0"), "calls": 0, "status": "no run line"})
        if rec["type"] == "call":
            cost = Decimal(rec["cost_usd"])
            run["cost"] += cost
            run["calls"] += 1
            by_step[rec["step"]] += cost
        elif rec["type"] == "run":
            run["status"] = rec["status"]
            run["items"] = rec["items"]
    total = sum((r["cost"] for r in runs.values()), Decimal("0"))
    return {"runs": runs, "by_step": dict(by_step), "total": total}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cost per run from a JSONL cost log.")
    parser.add_argument("log", type=Path)
    args = parser.parse_args(argv)
    s = summarise(args.log)
    print("| Run | Status | Calls | Cost (USD) |")
    print("| --- | --- | --- | --- |")
    for run_id, r in s["runs"].items():
        print(f"| {run_id} | {r['status']} | {r['calls']} | {r['cost']:.4f} |")
    print(f"\nTotal: ${s['total']:.4f}")
    for step, cost in sorted(s["by_step"].items(), key=lambda kv: kv[1], reverse=True):
        share = (cost / s["total"] * 100) if s["total"] else Decimal("0")
        print(f"  {step}: ${cost:.4f} ({share:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
