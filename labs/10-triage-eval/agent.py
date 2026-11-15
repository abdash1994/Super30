"""A minimal tool-using agent loop with a hard cap on iterations.

Each turn the model (any function ``llm(messages) -> dict``) returns either

    {"tool": "<name>", "args": {...}}        # call a tool, see the result next turn
    {"final": {"label": ..., "reply": ...}}  # stop and answer

The loop runs tools, feeds results back, and stops on ``final`` or after
``max_iterations`` turns, whichever comes first. Hitting the cap is not a crash:
the ticket is escalated to a human with the steps taken so far.

    python agent.py    # runs two scripted demo agents, no key needed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from triage import keyword_classifier

Message = dict[str, Any]
LLM = Callable[[list[Message]], dict]


@dataclass
class AgentResult:
    status: str  # "done" | "escalated"
    reason: str  # "final_answer" | "max_iterations" | "bad_model_output"
    iterations: int
    final: dict | None = None
    tool_calls: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)


def default_tools() -> dict[str, Callable[..., Any]]:
    """Tools the demo agent may call. Fake data, no network."""
    accounts = {"acme": {"plan": "annual", "seats": 40, "status": "active"}}
    return {
        "classify_ticket": lambda text: keyword_classifier(text),
        "lookup_account": lambda account_id: accounts.get(account_id, {"error": "not found"}),
    }


def run_agent(
    ticket: str,
    llm: LLM,
    tools: dict[str, Callable[..., Any]] | None = None,
    max_iterations: int = 5,
) -> AgentResult:
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    tools = default_tools() if tools is None else tools
    messages: list[Message] = [{"role": "user", "content": ticket}]
    calls: list[str] = []

    for turn in range(1, max_iterations + 1):
        action = llm(messages)
        if not isinstance(action, dict):
            return AgentResult("escalated", "bad_model_output", turn, None, calls, messages)
        if "final" in action:
            messages.append({"role": "assistant", "final": action["final"]})
            return AgentResult("done", "final_answer", turn, action["final"], calls, messages)
        if "tool" not in action:
            return AgentResult("escalated", "bad_model_output", turn, None, calls, messages)

        name, args = action["tool"], action.get("args") or {}
        calls.append(name)
        messages.append({"role": "assistant", "tool": name, "args": args})
        if name not in tools:
            observation: Any = {"error": f"unknown tool '{name}'", "available": sorted(tools)}
        else:
            try:
                observation = tools[name](**args)
            except Exception as exc:  # a failing tool is information for the model, not a crash
                observation = {"error": f"{type(exc).__name__}: {exc}"}
        messages.append({"role": "tool", "name": name, "content": observation})

    return AgentResult("escalated", "max_iterations", max_iterations, None, calls, messages)


def scripted_llm(actions: list[dict]) -> LLM:
    """A fake model that plays back fixed actions, then repeats the last one."""
    state = {"i": 0}

    def llm(messages: list[Message]) -> dict:
        action = actions[min(state["i"], len(actions) - 1)]
        state["i"] += 1
        return action

    return llm


if __name__ == "__main__":
    ticket = "We were billed for 40 seats but only use 25. Account: acme"
    good = scripted_llm([
        {"tool": "classify_ticket", "args": {"text": ticket}},
        {"tool": "lookup_account", "args": {"account_id": "acme"}},
        {"final": {"label": "billing", "reply": "Routing to billing to review your 40 seats."}},
    ])
    stuck = scripted_llm([{"tool": "lookup_account", "args": {"account_id": "acme"}}])
    for name, llm in [("well-behaved", good), ("stuck in a loop", stuck)]:
        r = run_agent(ticket, llm, max_iterations=5)
        print(f"{name:16} status={r.status:9} reason={r.reason:14} "
              f"iterations={r.iterations} tool_calls={len(r.tool_calls)}")
