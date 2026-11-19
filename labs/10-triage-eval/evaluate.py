"""Score a ticket classifier on the 50 labelled tickets in tickets.json.

    python evaluate.py      # keyword baseline, no key needed (what CI runs)

Prints accuracy, per-label precision and recall, and every miss.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from triage import LABELS, NEEDS_HUMAN, keyword_classifier

TICKETS = json.loads((Path(__file__).parent / "tickets.json").read_text())


@dataclass
class Report:
    total: int = 0
    correct: int = 0
    needs_human: int = 0
    # confusion[gold][predicted] = count
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    misses: list[tuple[int, str, str]] = field(default_factory=list)  # (id, gold, predicted)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def precision(self, label: str) -> float:
        predicted = sum(row.get(label, 0) for row in self.confusion.values())
        return self.confusion.get(label, {}).get(label, 0) / predicted if predicted else 0.0

    def recall(self, label: str) -> float:
        actual = sum(self.confusion.get(label, {}).values())
        return self.confusion.get(label, {}).get(label, 0) / actual if actual else 0.0


def evaluate(classify: Callable[[str], str], tickets: list[dict] = TICKETS) -> Report:
    report = Report()
    for ticket in tickets:
        gold, predicted = ticket["label"], classify(ticket["text"])
        report.total += 1
        row = report.confusion.setdefault(gold, {})
        row[predicted] = row.get(predicted, 0) + 1
        if predicted == gold:
            report.correct += 1
        else:
            report.misses.append((ticket["id"], gold, predicted))
            report.needs_human += predicted == NEEDS_HUMAN
    return report


def format_report(report: Report) -> str:
    lines = [
        f"Accuracy: {report.correct}/{report.total} = {report.accuracy:.0%}",
        f"Sent to a human (no label): {report.needs_human}",
        "",
        "| Label | Precision | Recall |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {l} | {report.precision(l):.0%} | {report.recall(l):.0%} |" for l in LABELS]
    if report.misses:
        lines += ["", "Misses (id: expected -> predicted):"]
        lines += [f"  {i}: {gold} -> {pred}" for i, gold, pred in report.misses]
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(evaluate(keyword_classifier)))
