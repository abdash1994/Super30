"""Run the 12 questions through the guarded text-to-SQL flow and print a scorecard.

    python demo.py

The model is faked with the stand-in answers in eval_cases.py, so this needs
no key and no network. Swap ``fake_llm`` for a real client to test a model.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from eval_cases import CASES
from text_to_sql import ask, seed


def fake_llm_for(cases):
    by_question = {c["question"]: c["model_sql"] for c in cases}

    def llm(prompt: str) -> str:
        question = prompt.rsplit("Question:", 1)[1].rsplit("SQL:", 1)[0].strip()
        return by_question[question]

    return llm


@dataclass
class Scorecard:
    correct: int = 0
    wrong: int = 0
    blocked: int = 0
    missed: int = 0  # a dangerous query that was not stopped
    false_blocks: int = 0  # a good question that was stopped
    stopped_by: dict | None = None
    lines: list | None = None


def evaluate(db_path: Path, cases=CASES, validate: bool = True) -> Scorecard:
    llm = fake_llm_for(cases)
    trusted = sqlite3.connect(db_path)
    card = Scorecard(stopped_by={}, lines=[])
    for case in cases:
        answer = ask(case["question"], llm, db_path, validate=validate)
        if case["expect"] == "block":
            if answer.status == "blocked":
                card.blocked += 1
                card.stopped_by[answer.stopped_by] = card.stopped_by.get(answer.stopped_by, 0) + 1
                verdict = f"blocked by {answer.stopped_by}"
            else:
                card.missed += 1
                verdict = "NOT BLOCKED"
        elif answer.status != "ok":
            card.false_blocks += 1
            verdict = f"wrongly stopped ({answer.status})"
        else:
            expected = [tuple(r) for r in trusted.execute(case["reference_sql"]).fetchall()]
            if answer.rows == expected:
                card.correct += 1
                verdict = "correct"
            else:
                card.wrong += 1
                verdict = f"wrong: got {answer.rows}, expected {expected}"
        card.lines.append((case["id"], case["question"], verdict))
    trusted.close()
    return card


def report(card: Scorecard) -> str:
    out = ["| # | Question | Outcome |", "| --- | --- | --- |"]
    out += [f"| {i} | {q} | {v} |" for i, q, v in card.lines]
    safe = card.correct + card.wrong + card.false_blocks
    danger = card.blocked + card.missed
    out += [
        "",
        f"Safe questions answered correctly: {card.correct}/{safe}",
        f"Dangerous answers stopped: {card.blocked}/{danger} "
        + ", ".join(f"{k}: {v}" for k, v in sorted(card.stopped_by.items())),
    ]
    return "\n".join(out)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        db = seed(Path(tmp) / "shop.db")
        print(report(evaluate(db)))
        print("\nSame run with the validator switched off:")
        print(report(evaluate(db, validate=False)).split("\n\n", 1)[1])
