"""Run the detector at three thresholds, print a table, and save chart.png."""

from __future__ import annotations

from chart import save_chart
from data import INCIDENTS, incident_days, make_orders
from detector import flagged, precision_recall, rolling_zscores

WINDOW = 14
THRESHOLDS = (2.0, 2.5, 3.0)


def rows():
    series = make_orders()
    out = []
    for t in THRESHOLDS:
        found = flagged(rolling_zscores(series, WINDOW, t))
        p, r = precision_recall(found, incident_days())
        caught = len(set(found) & set(incident_days()))
        out.append((t, len(found), caught, len(found) - caught, p, r))
    return out


def main() -> None:
    print(f"90 days of orders, window {WINDOW} days, {len(INCIDENTS)} injected incidents\n")
    print("| Threshold | Alerts | Incidents caught | False alarms | Precision | Recall |")
    print("| --- | --- | --- | --- | --- | --- |")
    for t, alerts, caught, false_alarms, p, r in rows():
        print(f"| {t:g} | {alerts} | {caught} of {len(INCIDENTS)} | {false_alarms} | {p:.0%} | {r:.0%} |")
    points = rolling_zscores(make_orders(), WINDOW, 3.0)
    save_chart(points, "chart.png", 3.0, "Orders per day, rolling z-score (window 14, threshold 3)")
    print("\nSaved chart.png")


if __name__ == "__main__":
    main()
