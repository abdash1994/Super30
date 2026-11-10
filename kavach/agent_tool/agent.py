"""A minimal agent loop that lets an LLM use the KAVACH scoring tool.

The LLM is anything with a `respond(messages, tools) -> dict` method, so tests
pass in a scripted fake and no API key or network is needed. A reply is either
{"type": "tool_call", "name": ..., "arguments": {...}} or
{"type": "text", "text": ...}.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Protocol


class LLM(Protocol):
    def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]: ...


def run_agent(
    llm: LLM,
    user_message: str,
    tools: dict[str, tuple[dict[str, Any], Callable[[dict[str, Any]], dict[str, Any]]]],
    *,
    max_steps: int = 4,
) -> dict[str, Any]:
    """Run until the LLM answers in text, or stop after max_steps tool calls.

    `tools` maps a tool name to (tool spec, callable). Returns the final text
    plus the full message list, so a caller can audit every tool result.
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    specs = [spec for spec, _ in tools.values()]

    for _ in range(max_steps):
        reply = llm.respond(messages, specs)
        if reply.get("type") == "text":
            messages.append({"role": "assistant", "content": reply["text"]})
            return {"answer": reply["text"], "messages": messages}

        name = reply.get("name")
        messages.append({"role": "assistant", "tool_call": reply})
        if name not in tools:
            result = {"ok": False, "error": {"code": "unknown_tool", "message": f"No tool named {name!r}",
                                             "retryable": False}}
        else:
            result = tools[name][1](reply.get("arguments") or {})
        messages.append({"role": "tool", "name": name, "content": json.dumps(result, default=str)})

    return {"answer": None, "messages": messages, "stopped": "max_steps"}
