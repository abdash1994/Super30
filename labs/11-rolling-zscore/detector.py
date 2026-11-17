"""Rolling z-score anomaly detector.

For each point, compare it with the mean and standard deviation of the
`window` points *before* it (never including itself), and flag it when
|z| is above `threshold`. Pure Python, no numpy needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    index: int
    value: float
    mean: float | None  # None during warm-up
    std: float | None
    z: float | None
    is_anomaly: bool


def _mean_std(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    # Sample standard deviation (n - 1), the usual choice for a baseline.
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(var)


def rolling_zscores(series: list[float], window: int = 14, threshold: float = 3.0) -> list[Point]:
    """Score every point against the `window` points before it.

    The first `window` points are warm-up: there is no baseline yet, so they
    get z=None and are never flagged. A flat baseline (std == 0) also gives
    z=None, because "any change at all" is not a useful alert.
    """
    if window < 2:
        raise ValueError("window must be at least 2")
    if threshold <= 0:
        raise ValueError("threshold must be positive")

    points: list[Point] = []
    for i, value in enumerate(series):
        if i < window:
            points.append(Point(i, value, None, None, None, False))
            continue
        mean, std = _mean_std(series[i - window : i])
        if std == 0:
            points.append(Point(i, value, mean, std, None, False))
            continue
        z = (value - mean) / std
        points.append(Point(i, value, mean, std, z, abs(z) > threshold))
    return points


def flagged(points: list[Point]) -> list[int]:
    return [p.index for p in points if p.is_anomaly]


def precision_recall(predicted: list[int], actual: list[int]) -> tuple[float, float]:
    """Precision: of the alerts raised, how many were real.
    Recall: of the real incidents, how many raised an alert."""
    pred, true = set(predicted), set(actual)
    hits = len(pred & true)
    precision = hits / len(pred) if pred else 1.0
    recall = hits / len(true) if true else 1.0
    return precision, recall
