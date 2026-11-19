import pytest

from agent import run_agent, scripted_llm

TICKET = "We were billed for 40 seats but only use 25. Account: acme"


def test_agent_uses_tools_then_finishes():
    llm = scripted_llm([
        {"tool": "classify_ticket", "args": {"text": TICKET}},
        {"tool": "lookup_account", "args": {"account_id": "acme"}},
        {"final": {"label": "billing", "reply": "Routing to billing."}},
    ])
    result = run_agent(TICKET, llm, max_iterations=5)
    assert (result.status, result.reason, result.iterations) == ("done", "final_answer", 3)
    assert result.tool_calls == ["classify_ticket", "lookup_account"]
    assert result.final["label"] == "billing"
    observations = [m["content"] for m in result.messages if m["role"] == "tool"]
    assert observations == ["billing", {"plan": "annual", "seats": 40, "status": "active"}]


def test_looping_agent_is_stopped_at_the_cap_and_escalated():
    calls = []
    tools = {"lookup_account": lambda account_id: calls.append(account_id) or {"seats": 40}}
    llm = scripted_llm([{"tool": "lookup_account", "args": {"account_id": "acme"}}])
    result = run_agent(TICKET, llm, tools=tools, max_iterations=4)
    assert (result.status, result.reason, result.iterations) == ("escalated", "max_iterations", 4)
    assert len(calls) == 4  # the tool ran exactly cap times, never more
    assert result.final is None


@pytest.mark.parametrize("cap", [1, 3, 10])
def test_model_is_called_at_most_cap_times(cap):
    count = {"n": 0}

    def llm(messages):
        count["n"] += 1
        return {"tool": "classify_ticket", "args": {"text": TICKET}}

    run_agent(TICKET, llm, max_iterations=cap)
    assert count["n"] == cap


def test_final_on_the_last_allowed_turn_still_counts_as_done():
    llm = scripted_llm([{"tool": "classify_ticket", "args": {"text": TICKET}}, {"final": {"label": "billing"}}])
    assert run_agent(TICKET, llm, max_iterations=2).status == "done"


def test_unknown_tool_is_reported_back_to_the_model_not_raised():
    llm = scripted_llm([{"tool": "refund_customer", "args": {}}, {"final": {"label": "billing"}}])
    result = run_agent(TICKET, llm)
    error = result.messages[2]["content"]
    assert "unknown tool" in error["error"]
    assert "lookup_account" in error["available"]
    assert result.status == "done"


def test_failing_tool_becomes_an_error_observation():
    def broken(**kwargs):
        raise TimeoutError("billing API did not answer")

    llm = scripted_llm([{"tool": "lookup_account", "args": {}}, {"final": {"label": "billing"}}])
    result = run_agent(TICKET, llm, tools={"lookup_account": broken})
    assert result.messages[2]["content"] == {"error": "TimeoutError: billing API did not answer"}
    assert result.status == "done"


def test_garbage_model_output_escalates_immediately():
    result = run_agent(TICKET, lambda messages: "I think it's billing")
    assert (result.status, result.reason, result.iterations) == ("escalated", "bad_model_output", 1)
    result = run_agent(TICKET, lambda messages: {"thought": "hmm"})
    assert result.reason == "bad_model_output"


def test_cap_below_one_is_rejected():
    with pytest.raises(ValueError):
        run_agent(TICKET, scripted_llm([{"final": {}}]), max_iterations=0)
