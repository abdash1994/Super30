"""Support ticket triage: put each ticket into one of five queues.

Two classifiers share one signature, ``classify(text) -> label``:

* ``keyword_classifier``: a rule-based baseline, no key, deterministic.
* ``llm_classifier(llm)``: wraps any function that takes a prompt and returns
  text (a real LLM in production, a fake in tests). The answer is checked
  against the allowed labels, and anything else becomes ``needs_human``.
"""

from __future__ import annotations

import re
from typing import Callable

LABELS = ("billing", "account_access", "bug", "feature_request", "cancellation")
NEEDS_HUMAN = "needs_human"

# Keyword -> weight per label. Written from general support experience, NOT
# tuned on tickets.json: tuning rules on the eval set would make its score a lie.
KEYWORDS: dict[str, dict[str, int]] = {
    "cancellation": {"cancel": 3, "close my account": 3, "terminate": 3, "unsubscribe": 3},
    "billing": {
        "charge": 2, "refund": 2, "invoice": 2, "payment": 2, "billed": 2,
        "billing": 2, "receipt": 2, "card": 1, "price": 1,
    },
    "account_access": {
        "log in": 3, "login": 3, "sign in": 3, "password": 3, "locked": 3,
        "two-factor": 3, "sso": 3, "access": 2,
    },
    "bug": {"error": 3, "crash": 3, "broken": 3, "fails": 2, "not loading": 3, "blank": 2},
    "feature_request": {
        "add": 1, "would be": 2, "would love": 3, "feature": 3, "any plans": 3,
        "i wish": 3, "support": 1,
    },
}

# When scores tie, the earlier label wins (cancelling is the costliest to miss).
TIE_ORDER = ("cancellation", "bug", "account_access", "billing", "feature_request")


def keyword_scores(text: str) -> dict[str, int]:
    lowered = text.lower()
    return {
        label: sum(w for phrase, w in words.items() if phrase in lowered)
        for label, words in KEYWORDS.items()
    }


def keyword_classifier(text: str) -> str:
    scores = keyword_scores(text)
    best = max(scores.values())
    if best == 0:
        return NEEDS_HUMAN
    return next(label for label in TIE_ORDER if scores[label] == best)


PROMPT = (
    "Classify this support ticket into exactly one of: "
    + ", ".join(LABELS)
    + ".\nAnswer with the label only.\n\nTicket: {ticket}"
)


def llm_classifier(llm: Callable[[str], str]) -> Callable[[str], str]:
    """Turn a text-in, text-out LLM function into a classifier that only ever
    returns an allowed label or ``needs_human``."""

    def classify(text: str) -> str:
        raw = llm(PROMPT.format(ticket=text))
        answer = re.sub(r"[^a-z_]", "", (raw or "").strip().lower())
        return answer if answer in LABELS else NEEDS_HUMAN

    return classify
