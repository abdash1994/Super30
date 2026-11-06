"""Lab 03: AI cost calculator.

cost per request = input_tokens x input_price + output_tokens x output_price
(prices are per 1 million tokens, as most providers publish them)
cost per month   = cost per request x requests per day x days

Prices are inputs, never hard-coded, because they change. Money maths uses
Decimal so 0.1 + 0.2 really is 0.3.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

PER_MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class Model:
    name: str
    input_price: Decimal  # USD per 1M input tokens
    output_price: Decimal  # USD per 1M output tokens


@dataclass(frozen=True)
class Estimate:
    model: str
    per_request: Decimal
    per_1k_requests: Decimal
    per_day: Decimal
    per_month: Decimal


def _non_negative(value: str, label: str) -> Decimal:
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{label} must be a number, got {value!r}") from None
    if not number.is_finite() or number < 0:
        raise ValueError(f"{label} must be zero or more, got {value!r}")
    return number


def parse_model(spec: str) -> Model:
    """Parse 'name:input_price:output_price', e.g. 'small:0.15:0.60'."""
    parts = spec.split(":")
    if len(parts) != 3 or not parts[0].strip():
        raise ValueError(
            f"model must look like name:input_price:output_price, got {spec!r}"
        )
    name, inp, out = parts
    return Model(
        name=name.strip(),
        input_price=_non_negative(inp, f"{name} input price"),
        output_price=_non_negative(out, f"{name} output price"),
    )


def estimate(
    model: Model,
    input_tokens: int,
    output_tokens: int,
    requests_per_day: int,
    days: int = 30,
) -> Estimate:
    for label, value in (
        ("input tokens", input_tokens),
        ("output tokens", output_tokens),
        ("requests per day", requests_per_day),
        ("days", days),
    ):
        if value < 0:
            raise ValueError(f"{label} must be zero or more, got {value}")

    per_request = (
        Decimal(input_tokens) * model.input_price
        + Decimal(output_tokens) * model.output_price
    ) / PER_MILLION
    per_day = per_request * requests_per_day
    return Estimate(
        model=model.name,
        per_request=per_request,
        per_1k_requests=per_request * 1000,
        per_day=per_day,
        per_month=per_day * days,
    )


def money(value: Decimal, places: int = 2) -> str:
    """Format USD. Per-request costs are fractions of a cent, so they get 6 places."""
    step = Decimal(1).scaleb(-places)
    return f"${value.quantize(step, rounding=ROUND_HALF_UP):,}"


def render_table(estimates: list[Estimate], days: int) -> str:
    headers = ["Model", "Per request", "Per 1k requests", "Per day", f"Per {days} days"]
    rows = [
        [e.model, money(e.per_request, 6), money(e.per_1k_requests), money(e.per_day), money(e.per_month)]
        for e in estimates
    ]
    widths = [max(len(str(c)) for c in col) for col in zip(headers, *rows)]

    def line(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

    out = [line(headers), "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    out += [line(r) for r in rows]
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Estimate LLM spend: tokens per request x price x volume."
    )
    p.add_argument("--input-tokens", type=int, required=True, help="input (prompt) tokens per request")
    p.add_argument("--output-tokens", type=int, required=True, help="output (completion) tokens per request")
    p.add_argument("--requests-per-day", type=int, required=True)
    p.add_argument("--days", type=int, default=30, help="days in the period (default 30)")
    p.add_argument(
        "--model",
        action="append",
        required=True,
        metavar="NAME:IN:OUT",
        help="USD per 1M input and output tokens, e.g. small:0.15:0.60 (repeat to compare)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        models = [parse_model(spec) for spec in args.model]
        estimates = [
            estimate(m, args.input_tokens, args.output_tokens, args.requests_per_day, args.days)
            for m in models
        ]
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(render_table(estimates, args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
