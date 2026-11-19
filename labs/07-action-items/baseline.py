"""A rule-based stand-in for an LLM, so the evaluation runs in CI with no key.

It looks for a handful of phrasings ("I'll ...", "Ravi, can you ...",
"Ravi will ...", "someone needs to ...") and emits the same JSON an LLM would.
It is deliberately simple: its score is the floor a real model has to beat.
"""

from __future__ import annotations

import json
import re

UNASSIGNED = "unassigned"
DAYS = r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
DUE = re.compile(
    rf"\s*\b(?:by|before|on)\s+(tomorrow|next week|end of (?:the )?(?:day|week|month)|{DAYS})\b",
    re.IGNORECASE,
)
UNOWNED = re.compile(
    r"\b(?:someone|somebody|anyone) (?:needs to|should|has to|must)\s+(.+)"
    r"|\bcan (?:someone|anyone|somebody)\s+(.+)"
    r"|\bwe (?:still )?need to\s+(.+)",
    re.IGNORECASE,
)


def _item(task: str, owner: str) -> dict | None:
    due = None
    match = DUE.search(task)
    if match:
        due = match.group(1)
        task = (task[: match.start()] + task[match.end():]).strip()
    task = task.strip(" ,;")
    if len(task) < 3:
        return None
    return {"task": task[0].upper() + task[1:], "owner": owner, "due": due}


def _from_sentence(sentence: str, speaker: str, attendees: list[str]) -> dict | None:
    names = "|".join(re.escape(a) for a in attendees)
    if m := re.search(r"\bI(?:'ll| will)\s+(.+)", sentence):
        return _item(m.group(1), speaker)
    if m := re.match(rf"^({names}),\s+(?:can|could) you\s+(.+)", sentence):
        return _item(m.group(2), m.group(1))
    if m := re.search(rf"\b({names}) will\s+(.+)", sentence):
        return _item(m.group(2), m.group(1))
    if m := UNOWNED.search(sentence):
        return _item(next(g for g in m.groups() if g), UNASSIGNED)
    return None


def extract_items(transcript: str, attendees: list[str]) -> list[dict]:
    items = []
    for line in transcript.splitlines():
        speaker, sep, text = line.partition(":")
        if not sep:
            continue
        for sentence in re.split(r"(?<=[.?!])\s+", text.strip()):
            item = _from_sentence(sentence.rstrip(".?!"), speaker.strip(), attendees)
            if item:
                items.append(item)
    return items


def baseline_llm(transcript: str, attendees: list[str]):
    """Return an llm(prompt) -> str function that answers for this transcript."""

    def llm(prompt: str) -> str:
        return json.dumps({"action_items": extract_items(transcript, attendees)})

    return llm
