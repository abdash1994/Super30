"""Draw the series, the rolling baseline band and the flagged points to a PNG."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # no screen needed, works in CI
import matplotlib.pyplot as plt  # noqa: E402

from detector import Point  # noqa: E402


def save_chart(points: list[Point], path: str, threshold: float, title: str) -> str:
    xs = [p.index for p in points]
    ys = [p.value for p in points]
    scored = [p for p in points if p.mean is not None and p.std is not None]
    bx = [p.index for p in scored]
    lo = [p.mean - threshold * p.std for p in scored]
    hi = [p.mean + threshold * p.std for p in scored]
    mid = [p.mean for p in scored]
    ax_pts = [p for p in points if p.is_anomaly]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(bx, lo, hi, color="#9ecae1", alpha=0.4, label=f"normal range (mean ± {threshold:g} std)")
    ax.plot(bx, mid, color="#3182bd", linewidth=1, label="rolling mean")
    ax.plot(xs, ys, color="#333333", linewidth=1.2, label="orders per day")
    ax.scatter([p.index for p in ax_pts], [p.value for p in ax_pts], color="#d62728", zorder=3, s=40, label="flagged")
    ax.set_xlabel("day")
    ax.set_ylabel("orders")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
