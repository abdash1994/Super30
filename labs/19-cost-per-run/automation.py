"""A small daily automation: classify each support ticket, draft a reply for the real ones.

The model client is anything with `complete(model, prompt) -> (text, usage)`, where
usage is {"input_tokens": int, "output_tokens": int} as real APIs return it.
`FakeLLM` stands in for the API so the lab runs with no key and no network.
"""

from __future__ import annotations

from typing import Protocol

from cost_log import RunLogger

CLASSIFY_PROMPT = "Label this ticket as one of: billing, bug, spam.\n\n"
REPLY_PROMPT = "Write a short, polite reply to this customer ticket.\n\n"


class LLM(Protocol):
    def complete(self, model: str, prompt: str) -> tuple[str, dict]: ...


class FakeLLM:
    """Deterministic stand-in: about 4 characters per token, fixed reply lengths."""

    OUTPUT_TOKENS = {"classify": 3, "reply": 150}

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, model: str, prompt: str) -> tuple[str, dict]:
        self.calls += 1
        if prompt.startswith(CLASSIFY_PROMPT):
            text = "spam" if "win a prize" in prompt.lower() else (
                "billing" if "invoice" in prompt.lower() or "charged" in prompt.lower() else "bug")
            out = self.OUTPUT_TOKENS["classify"]
        else:
            text = "Thanks for reaching out. We are looking into this and will update you today."
            out = self.OUTPUT_TOKENS["reply"]
        return text, {"input_tokens": len(prompt) // 4, "output_tokens": out}


def run_triage(tickets: list[str], llm: LLM, logger: RunLogger,
               classify_model: str = "small", reply_model: str = "large") -> list[dict]:
    """Classify with the cheap model; only non-spam tickets get a (costly) drafted reply."""
    results = []
    for ticket in tickets:
        label, usage = llm.complete(classify_model, CLASSIFY_PROMPT + ticket)
        logger.record("classify", classify_model, usage)
        reply = None
        if label != "spam":
            reply, usage = llm.complete(reply_model, REPLY_PROMPT + ticket)
            logger.record("reply", reply_model, usage)
        logger.items += 1
        results.append({"ticket": ticket, "label": label, "reply": reply})
    return results
