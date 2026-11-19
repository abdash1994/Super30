"""Lab 07: meeting transcript to action items, as JSON that must match a schema.

The pipeline is the same whichever "model" sits in the middle:

    transcript -> prompt -> model text -> json.loads -> schema check -> owner guard

* The model is any function `llm(prompt) -> str`. Tests pass a fake one, the
  evaluation uses a rule-based baseline, and `--live` calls a real LLM.
* Output that is not JSON, or does not match schema.json, gets ONE retry with
  the error fed back. A second failure raises ExtractionError instead of
  passing bad data downstream.
* "unassigned" is a valid owner. If the model names someone who was not in the
  meeting, the owner guard replaces it with "unassigned" and records a warning,
  so nobody gets a task they never agreed to.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from jsonschema import Draft202012Validator

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / "schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
UNASSIGNED = "unassigned"

LLM = Callable[[str], str]


class ExtractionError(Exception):
    """The model did not return schema-valid JSON, even after one retry."""


@dataclass
class Result:
    action_items: list[dict]
    attempts: int
    warnings: list[str] = field(default_factory=list)


def build_prompt(transcript: str, attendees: list[str], error: str | None = None) -> str:
    prompt = (
        "Extract the action items from this meeting transcript.\n"
        "Reply with JSON only, matching this JSON Schema:\n"
        f"{json.dumps(SCHEMA)}\n\n"
        "Rules:\n"
        f"- owner must be one of: {', '.join(attendees)}, or \"{UNASSIGNED}\".\n"
        f"- Use \"{UNASSIGNED}\" when nobody clearly took the task. Never guess an owner.\n"
        "- due is the deadline as said (e.g. \"Friday\"), or null.\n"
        "- Ideas, opinions and things already done are not action items.\n\n"
        f"Transcript:\n{transcript}\n"
    )
    if error:
        prompt += f"\nYour previous reply was rejected: {error}\nReturn corrected JSON only.\n"
    return prompt


def check(text: str) -> tuple[dict | None, str | None]:
    """Parse and validate model text. Returns (data, None) or (None, error)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"not valid JSON ({exc.msg} at position {exc.pos})"
    errors = sorted(VALIDATOR.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.path) or "(root)"
        return None, f"schema error at {where}: {first.message}"
    return data, None


def guard_owners(items: list[dict], attendees: list[str]) -> tuple[list[dict], list[str]]:
    """Replace owners who were not in the meeting with "unassigned"."""
    by_lower = {a.lower(): a for a in attendees}
    cleaned, warnings = [], []
    for item in items:
        owner = item["owner"].strip()
        if owner.lower() == UNASSIGNED:
            owner = UNASSIGNED
        elif owner.lower() in by_lower:
            owner = by_lower[owner.lower()]
        else:
            warnings.append(f"owner {owner!r} was not an attendee; set to {UNASSIGNED}")
            owner = UNASSIGNED
        cleaned.append({**item, "owner": owner})
    return cleaned, warnings


def extract(transcript: str, attendees: list[str], llm: LLM, max_attempts: int = 2) -> Result:
    error = None
    for attempt in range(1, max_attempts + 1):
        data, error = check(llm(build_prompt(transcript, attendees, error)))
        if data is not None:
            items, warnings = guard_owners(data["action_items"], attendees)
            return Result(items, attempt, warnings)
    raise ExtractionError(f"gave up after {max_attempts} attempts: {error}")


def anthropic_llm(prompt: str) -> str:  # pragma: no cover - needs a key and network
    """Live model. Needs ANTHROPIC_API_KEY and LAB07_MODEL (a model id you have access to)."""
    body = json.dumps(
        {
            "model": os.environ["LAB07_MODEL"],
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        reply = json.load(response)
    text = "".join(block.get("text", "") for block in reply["content"])
    # Some models wrap JSON in a ```json fence; strip it before the schema check.
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
