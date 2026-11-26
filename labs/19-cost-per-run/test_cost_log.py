import json
from decimal import Decimal

import pytest

from automation import FakeLLM, run_triage
from cost_log import BudgetExceeded, RunLogger, UnknownModel, call_cost, main, read_log, summarise
from demo import tickets


def test_call_cost_hand_checked():
    # 1,000 in x $3/1M + 500 out x $15/1M = 0.003 + 0.0075
    assert call_cost("large", 1000, 500) == Decimal("0.0105")


def test_call_cost_no_float_drift():
    prices = {"x": (Decimal("0.1"), Decimal("0.2"))}
    assert call_cost("x", 1_000_000, 1_000_000, prices) == Decimal("0.3")


def test_unknown_model_is_refused_not_logged_as_free(tmp_path):
    log = tmp_path / "runs.jsonl"
    with pytest.raises(UnknownModel):
        with RunLogger(log) as lg:
            lg.record("classify", "mystery-model", {"input_tokens": 10, "output_tokens": 1})
    recs = read_log(log)
    assert [r["type"] for r in recs] == ["run"]
    assert recs[0]["status"] == "failed"


def test_negative_tokens_rejected():
    with pytest.raises(ValueError):
        call_cost("small", -1, 0)


def test_every_call_and_the_run_are_logged(tmp_path):
    log = tmp_path / "runs.jsonl"
    llm = FakeLLM()
    with RunLogger(log, run_id="r1") as lg:
        run_triage(tickets(4), llm, lg)
    recs = read_log(log)
    calls = [r for r in recs if r["type"] == "call"]
    # 4 classify + 3 replies (the spam ticket gets no reply)
    assert len(calls) == llm.calls == 7
    assert recs[-1]["type"] == "run"
    assert recs[-1]["status"] == "ok"
    assert recs[-1]["items"] == 4
    assert Decimal(recs[-1]["cost_usd"]) == sum(Decimal(c["cost_usd"]) for c in calls)


def test_log_lines_are_valid_json_with_cost_as_string(tmp_path):
    log = tmp_path / "runs.jsonl"
    with RunLogger(log) as lg:
        run_triage(tickets(2), FakeLLM(), lg)
    for line in log.read_text().splitlines():
        rec = json.loads(line)
        assert isinstance(rec["cost_usd"], str)


def test_budget_stops_the_run_and_overshoots_by_at_most_one_call(tmp_path):
    log = tmp_path / "runs.jsonl"
    budget = Decimal("0.25")
    with RunLogger(log, budget_usd=budget) as lg:  # BudgetExceeded is swallowed by the logger
        run_triage(tickets(200), FakeLLM(), lg)
    assert lg.status == "stopped_budget"
    assert lg.items < 200
    biggest_call = call_cost("large", 200, FakeLLM.OUTPUT_TOKENS["reply"])
    assert budget < lg.total_usd <= budget + biggest_call
    assert read_log(log)[-1]["status"] == "stopped_budget"


def test_other_errors_still_raise_and_are_marked_failed(tmp_path):
    class Broken:
        def complete(self, model, prompt):
            raise TimeoutError("api timed out")

    log = tmp_path / "runs.jsonl"
    with pytest.raises(TimeoutError):
        with RunLogger(log) as lg:
            run_triage(tickets(1), Broken(), lg)
    assert read_log(log)[-1]["status"] == "failed"


def test_cost_per_ticket_matches_demo_and_cheap_model_is_10x_cheaper(tmp_path):
    log = tmp_path / "runs.jsonl"
    with RunLogger(log) as big:
        run_triage(tickets(20), FakeLLM(), big)
    with RunLogger(log) as small:
        run_triage(tickets(20), FakeLLM(), small, reply_model="small")
    assert big.total_usd / big.items == pytest.approx(Decimal("0.00184"), abs=Decimal("0.00001"))
    assert big.total_usd > 10 * small.total_usd


def test_summarise_by_run_and_step(tmp_path):
    log = tmp_path / "runs.jsonl"
    for rid in ("a", "b"):
        with RunLogger(log, run_id=rid) as lg:
            run_triage(tickets(4), FakeLLM(), lg)
    s = summarise(log)
    assert set(s["runs"]) == {"a", "b"}
    assert s["runs"]["a"]["cost"] == s["runs"]["b"]["cost"]
    assert s["total"] == s["by_step"]["classify"] + s["by_step"]["reply"]
    assert s["by_step"]["reply"] > s["by_step"]["classify"]


def test_report_cli_prints_runs(tmp_path, capsys):
    log = tmp_path / "runs.jsonl"
    with RunLogger(log, run_id="cli-run") as lg:
        run_triage(tickets(3), FakeLLM(), lg)
    assert main([str(log)]) == 0
    out = capsys.readouterr().out
    assert "cli-run" in out and "Total: $" in out
