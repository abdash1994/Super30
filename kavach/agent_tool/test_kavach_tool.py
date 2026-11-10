"""Tests for the KAVACH agent tool. No network: httpx.MockTransport plays the API."""

import json

import httpx
import pytest

from agent import run_agent
from kavach_tool import TOOL_NAME, TOOL_SPEC, KavachScoreTool

ARGS = {"transaction_id": "txn_0001", "customer_id": "cust_0001", "amount_inr": "1499.00"}
SCORE = {"transaction_id": "txn_0001", "risk_score": 0.12, "decision": "approve"}


def make_tool(responses, **kwargs):
    """Build a tool whose fake API returns `responses` in order.

    Each item is an httpx.Response, or an exception class to raise instead.
    Returns (tool, list of requests seen, list of sleeps taken).
    """
    seen, sleeps = [], []
    queue = list(responses)

    def handler(request):
        seen.append(request)
        item = queue.pop(0)
        if isinstance(item, type) and issubclass(item, Exception):
            raise item("simulated", request=request)
        return item

    tool = KavachScoreTool("https://kavach.test", transport=httpx.MockTransport(handler),
                           sleep=sleeps.append, **kwargs)
    return tool, seen, sleeps


def test_success_returns_data_on_first_attempt():
    tool, seen, sleeps = make_tool([httpx.Response(200, json=SCORE)])
    result = tool(ARGS)
    assert result == {"ok": True, "attempts": 1, "data": SCORE}
    assert seen[0].method == "POST" and seen[0].url.path == "/v1/score"
    assert json.loads(seen[0].content) == ARGS
    assert sleeps == []


def test_every_attempt_carries_the_timeout():
    tool, seen, _ = make_tool([httpx.Response(200, json=SCORE)], timeout_s=1.5)
    tool(ARGS)
    assert seen[0].extensions["timeout"]["read"] == 1.5


def test_retries_a_503_then_succeeds_with_backoff():
    tool, seen, sleeps = make_tool([httpx.Response(503), httpx.Response(200, json=SCORE)])
    result = tool(ARGS)
    assert result["ok"] is True and result["attempts"] == 2
    assert sleeps == [0.5]


def test_retry_uses_the_same_idempotency_key():
    tool, seen, _ = make_tool([httpx.Response(502), httpx.Response(200, json=SCORE)])
    tool(ARGS)
    keys = {r.headers["Idempotency-Key"] for r in seen}
    assert keys == {"txn_0001"}


def test_timeouts_exhaust_retries_into_a_structured_error():
    tool, seen, sleeps = make_tool([httpx.ReadTimeout] * 3)
    result = tool(ARGS)
    assert result["ok"] is False
    assert result["error"]["code"] == "timeout"
    assert result["error"]["retryable"] is True
    assert result["error"]["attempts"] == 3
    assert len(seen) == 3
    assert sleeps == [0.5, 1.0]  # no sleep after the last attempt


def test_connection_failure_is_reported_as_unreachable():
    tool, _, _ = make_tool([httpx.ConnectError] * 3)
    result = tool(ARGS)
    assert result["error"]["code"] == "unreachable"
    assert result["error"]["retryable"] is True


def test_429_honours_retry_after_but_caps_it():
    tool, _, sleeps = make_tool(
        [httpx.Response(429, headers={"Retry-After": "30"}), httpx.Response(200, json=SCORE)],
        max_backoff_s=4.0,
    )
    assert tool(ARGS)["ok"] is True
    assert sleeps == [4.0]


def test_422_is_not_retried_and_passes_reasons_to_the_agent():
    body = {"detail": [{"loc": ["body", "amount_inr"], "msg": "Input should be greater than 0"}]}
    tool, seen, sleeps = make_tool([httpx.Response(422, json=body)])
    result = tool({**ARGS, "amount_inr": "-5"})
    assert len(seen) == 1 and sleeps == []
    assert result["error"]["code"] == "invalid_request"
    assert result["error"]["retryable"] is False
    assert result["error"]["status"] == 422
    assert result["error"]["details"] == body


def test_401_is_rejected_without_retry():
    tool, seen, _ = make_tool([httpx.Response(401, json={"detail": "bad key"})])
    result = tool(ARGS)
    assert len(seen) == 1
    assert result["error"]["code"] == "rejected"


def test_non_json_success_is_a_bad_response():
    tool, _, _ = make_tool([httpx.Response(200, text="<html>proxy page</html>")])
    result = tool(ARGS)
    assert result["error"]["code"] == "bad_response"


def test_missing_transaction_id_never_calls_the_api():
    tool, seen, _ = make_tool([])
    result = tool({"customer_id": "cust_0001"})
    assert seen == []
    assert result["error"]["code"] == "invalid_arguments"


def test_max_attempts_must_be_positive():
    with pytest.raises(ValueError):
        KavachScoreTool("https://kavach.test", max_attempts=0)


def test_api_key_is_sent_as_bearer_token():
    tool, seen, _ = make_tool([httpx.Response(200, json=SCORE)], api_key="test-key")
    tool(ARGS)
    assert seen[0].headers["Authorization"] == "Bearer test-key"


def test_tool_spec_is_well_formed():
    assert TOOL_SPEC["name"] == TOOL_NAME
    assert "transaction_id" in TOOL_SPEC["input_schema"]["required"]


# --- Agent loop, with the LLM mocked -------------------------------------------------


class ScriptedLLM:
    """Fake LLM: asks for the tool once, then writes an answer from the tool result."""

    def __init__(self, arguments):
        self.arguments = arguments
        self.calls = []

    def respond(self, messages, tools):
        self.calls.append(messages[:])
        if messages[-1]["role"] == "user":
            return {"type": "tool_call", "name": TOOL_NAME, "arguments": self.arguments}
        result = json.loads(messages[-1]["content"])
        if result["ok"]:
            return {"type": "text", "text": f"Decision: {result['data']['decision']}"}
        err = result["error"]
        return {"type": "text", "text": f"Could not score ({err['code']}, retryable={err['retryable']})"}


def test_agent_gets_the_score_and_answers():
    tool, _, _ = make_tool([httpx.Response(200, json=SCORE)])
    llm = ScriptedLLM(ARGS)
    out = run_agent(llm, "Should we approve txn_0001?", {TOOL_NAME: (TOOL_SPEC, tool)})
    assert out["answer"] == "Decision: approve"
    assert len(llm.calls) == 2


def test_agent_survives_an_outage_and_reads_the_structured_error():
    tool, _, _ = make_tool([httpx.ReadTimeout] * 3)
    llm = ScriptedLLM(ARGS)
    out = run_agent(llm, "Should we approve txn_0001?", {TOOL_NAME: (TOOL_SPEC, tool)})
    assert out["answer"] == "Could not score (timeout, retryable=True)"


def test_agent_unknown_tool_and_step_limit():
    class LoopingLLM:
        def respond(self, messages, tools):
            return {"type": "tool_call", "name": "no_such_tool", "arguments": {}}

    out = run_agent(LoopingLLM(), "hi", {}, max_steps=2)
    assert out["stopped"] == "max_steps"
    tool_msgs = [m for m in out["messages"] if m["role"] == "tool"]
    assert len(tool_msgs) == 2
    assert json.loads(tool_msgs[0]["content"])["error"]["code"] == "unknown_tool"
