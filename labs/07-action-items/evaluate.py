"""Score the extractor on the 10 labelled transcripts in samples.json.

    python evaluate.py           # rule-based baseline, no key needed (what CI runs)
    python evaluate.py --live    # a real LLM; needs ANTHROPIC_API_KEY and LAB07_MODEL

A predicted item matches an expected one when its task text contains all of
the expected keywords. Each expected item can be matched once.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from baseline import baseline_llm
from extract import ExtractionError, anthropic_llm, extract

SAMPLES = json.loads((Path(__file__).parent / "samples.json").read_text())


@dataclass(frozen=True)
class Score:
    samples: int
    schema_valid: int
    expected: int
    predicted: int
    matched: int
    owner_correct: int
    due_correct: int
    unassigned_expected: int
    unassigned_correct: int

    @property
    def precision(self) -> float:
        return self.matched / self.predicted if self.predicted else 1.0

    @property
    def recall(self) -> float:
        return self.matched / self.expected if self.expected else 1.0

    @property
    def owner_accuracy(self) -> float:
        return self.owner_correct / self.matched if self.matched else 0.0


def _norm(value):
    return value.strip().lower() if isinstance(value, str) else value


def match(predicted: list[dict], expected: list[dict]) -> list[tuple[dict, dict]]:
    pairs, used = [], set()
    for gold in expected:
        for i, item in enumerate(predicted):
            if i not in used and all(k.lower() in item["task"].lower() for k in gold["keywords"]):
                used.add(i)
                pairs.append((gold, item))
                break
    return pairs


def evaluate(make_llm, samples: list[dict] = SAMPLES) -> Score:
    totals = dict.fromkeys(
        ["schema_valid", "expected", "predicted", "matched", "owner_correct",
         "due_correct", "unassigned_expected", "unassigned_correct"], 0)
    for sample in samples:
        expected = sample["expected"]
        totals["expected"] += len(expected)
        totals["unassigned_expected"] += sum(g["owner"] == "unassigned" for g in expected)
        try:
            result = extract(sample["transcript"], sample["attendees"], make_llm(sample))
        except ExtractionError:
            continue  # counts as zero predictions and not schema-valid
        totals["schema_valid"] += 1
        totals["predicted"] += len(result.action_items)
        for gold, item in match(result.action_items, expected):
            totals["matched"] += 1
            totals["owner_correct"] += gold["owner"] == item["owner"]
            totals["due_correct"] += _norm(gold["due"]) == _norm(item["due"])
            totals["unassigned_correct"] += gold["owner"] == item["owner"] == "unassigned"
    return Score(samples=len(samples), **totals)


def report(score: Score) -> str:
    return "\n".join([
        f"Schema-valid replies : {score.schema_valid}/{score.samples}",
        f"Precision            : {score.matched}/{score.predicted} = {score.precision:.0%}",
        f"Recall               : {score.matched}/{score.expected} = {score.recall:.0%}",
        f"Owner correct        : {score.owner_correct}/{score.matched} = {score.owner_accuracy:.0%}",
        f"Due date correct     : {score.due_correct}/{score.matched}",
        f"'unassigned' kept    : {score.unassigned_correct}/{score.unassigned_expected}",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="use a real LLM instead of the baseline")
    args = parser.parse_args(argv)
    if args.live:
        score = evaluate(lambda sample: anthropic_llm)
    else:
        score = evaluate(lambda sample: baseline_llm(sample["transcript"], sample["attendees"]))
    print(report(score))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
