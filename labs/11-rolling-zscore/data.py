"""A seeded, deterministic series: 90 days of orders for a small online shop.

Normal days are about 200 orders with a gentle upward trend and random noise.
Three incidents are injected on known days, so the detector can be scored.
"""

from __future__ import annotations

import random

DAYS = 90

# day -> (change in orders, what happened)
INCIDENTS = {
    40: (+80, "duplicate orders from a payment retry bug"),
    62: (-70, "checkout button broken after a release"),
    75: (+60, "bot traffic placing fake orders"),
}


def make_orders(seed: int = 7) -> list[float]:
    rng = random.Random(seed)
    series = []
    for day in range(DAYS):
        value = 200 + 0.3 * day + rng.gauss(0, 8)
        if day in INCIDENTS:
            value += INCIDENTS[day][0]
        series.append(round(value, 1))
    return series


def incident_days() -> list[int]:
    return sorted(INCIDENTS)
