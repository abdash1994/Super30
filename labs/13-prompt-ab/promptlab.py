"""Score two prompt versions on the same eval set, item by item.

The flow a real project follows:

1. ``run_prompt(template, items, llm)`` sends every eval item through one
   prompt and saves the raw answers next to the SHA-256 of the prompt text.
2. ``load_outputs`` refuses answers whose saved hash does not match the prompt
   file on disk, so a score can never be quoted for a prompt that has since
   been edited.
3. ``score`` parses each answer strictly and counts correct, wrong and
   unparseable answers.
4. ``compare`` lines the two versions up item by item: what v2 fixed, what it
   broke, and whether it may ship.

``llm`` is any function ``prompt -> text``: a real model client in production,
a fake in the tests. Nothing here touches the network.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

LABELS = ("billing", "account_access", "bug", "feature_request", "cancellation")
INVALID = "invalid"

HERE = Path(__file__).parent


class StaleOutputsError(ValueError):
    """Saved answers were produced by a different prompt than the file on disk."""


def prompt_sha256(template: str) -> str:
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


def load_prompt(version: str, folder: Path = HERE / "prompts") -> str:
    return (folder / f"{version}.txt").read_text(encoding="utf-8")


def load_eval_set(path: Path = HERE / "eval_set.json") -> list[dict]:
    items = json.loads(path.read_text(encoding="utf-8"))
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("eval set has duplicate ids")
    for item in items:
        if item["label"] not in LABELS:
            raise ValueError(f"{item['id']}: unknown label {item['label']!r}")
    return items


def render(template: str, ticket: str) -> str:
    return template.replace("{ticket}", ticket)


def parse_label(answer: str) -> str:
    """Strict parser: the whole answer must be one allowed label.

    Case, surrounding spaces, quotes and a trailing full stop are forgiven.
    Anything else (a sentence, a synonym, two labels) is ``invalid``: code
    downstream cannot route "Probably the billing team" to a queue.
    """
    cleaned = answer.strip().strip("\"'`").strip().rstrip(".").strip().lower()
    return cleaned if cleaned in LABELS else INVALID


def run_prompt(template: str, items: Iterable[dict], llm: Callable[[str], str]) -> dict:
    """Send every item through one prompt. Returns the record to save as JSON."""
    return {
        "prompt_sha256": prompt_sha256(template),
        "outputs": {item["id"]: llm(render(template, item["text"])) for item in items},
    }


def load_outputs(version: str, folder: Path = HERE / "outputs",
                 prompts: Path = HERE / "prompts") -> dict[str, str]:
    record = json.loads((folder / f"{version}.json").read_text(encoding="utf-8"))
    expected = prompt_sha256(load_prompt(version, prompts))
    if record["prompt_sha256"] != expected:
        raise StaleOutputsError(
            f"outputs/{version}.json was made with a different prompt; "
            f"re-run prompts/{version}.txt before quoting its score"
        )
    return record["outputs"]


@dataclass
class Score:
    total: int
    correct: int
    wrong: int
    invalid: int
    verdicts: dict[str, bool] = field(default_factory=dict)  # id -> correct?

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def score(items: list[dict], outputs: dict[str, str]) -> Score:
    missing = [item["id"] for item in items if item["id"] not in outputs]
    if missing:
        raise ValueError(f"no answer for: {', '.join(missing)}")
    correct = wrong = invalid = 0
    verdicts: dict[str, bool] = {}
    for item in items:
        label = parse_label(outputs[item["id"]])
        ok = label == item["label"]
        verdicts[item["id"]] = ok
        if ok:
            correct += 1
        elif label == INVALID:
            invalid += 1
        else:
            wrong += 1
    return Score(len(items), correct, wrong, invalid, verdicts)


@dataclass
class Comparison:
    old: Score
    new: Score
    fixed: list[str]   # wrong in old, right in new
    broken: list[str]  # right in old, wrong in new
    max_broken: int

    @property
    def ship(self) -> bool:
        return self.new.correct > self.old.correct and len(self.broken) <= self.max_broken


def compare(items: list[dict], old_outputs: dict[str, str], new_outputs: dict[str, str],
            max_broken: int = 1) -> Comparison:
    """Item-by-item comparison. ``max_broken`` is how many regressions we accept."""
    old, new = score(items, old_outputs), score(items, new_outputs)
    ids = [item["id"] for item in items]
    fixed = [i for i in ids if not old.verdicts[i] and new.verdicts[i]]
    broken = [i for i in ids if old.verdicts[i] and not new.verdicts[i]]
    return Comparison(old, new, fixed, broken, max_broken)
