import json

import pytest

from compare import report
from promptlab import (
    INVALID,
    LABELS,
    StaleOutputsError,
    compare,
    load_eval_set,
    load_outputs,
    load_prompt,
    parse_label,
    prompt_sha256,
    render,
    run_prompt,
    score,
)

ITEMS = [
    {"id": "a", "text": "refund please", "label": "billing"},
    {"id": "b", "text": "app crashes", "label": "bug"},
    {"id": "c", "text": "cancel us", "label": "cancellation"},
]


# --- parsing -------------------------------------------------------------

@pytest.mark.parametrize("answer", ["billing", "Billing", " billing.\n", '"billing"', "`billing`"])
def test_parser_forgives_case_quotes_and_full_stop(answer):
    assert parse_label(answer) == "billing"


@pytest.mark.parametrize("answer", [
    "The billing team.", "Payments", "Account Access", "billing, bug", "", "account-access",
])
def test_parser_rejects_anything_that_is_not_one_label(answer):
    assert parse_label(answer) == INVALID


# --- scoring -------------------------------------------------------------

def test_score_splits_correct_wrong_and_invalid():
    s = score(ITEMS, {"a": "billing", "b": "feature_request", "c": "Cancel it"})
    assert (s.correct, s.wrong, s.invalid, s.total) == (1, 1, 1, 3)
    assert s.accuracy == pytest.approx(1 / 3)
    assert s.verdicts == {"a": True, "b": False, "c": False}


def test_score_refuses_missing_answers():
    with pytest.raises(ValueError, match="no answer for: c"):
        score(ITEMS, {"a": "billing", "b": "bug"})


def test_compare_lists_fixed_and_broken_items():
    old = {"a": "billing", "b": "Engineering", "c": "cancellation"}
    new = {"a": "billing", "b": "bug", "c": "billing"}
    result = compare(ITEMS, old, new, max_broken=1)
    assert result.fixed == ["b"]
    assert result.broken == ["c"]
    # Same number correct (2 vs 2): no improvement, so it does not ship.
    assert result.ship is False


def test_ship_rule_blocks_when_too_many_items_break():
    old = {"a": "billing", "b": "x", "c": "x"}
    new = {"a": "bug", "b": "bug", "c": "cancellation"}
    # More correct (2 vs 1), but item "a" broke.
    assert compare(ITEMS, old, new, max_broken=0).ship is False
    assert compare(ITEMS, old, new, max_broken=1).ship is True


def test_ship_rule_allows_a_clear_win():
    old = {"a": "x", "b": "x", "c": "cancellation"}
    new = {"a": "billing", "b": "bug", "c": "cancellation"}
    assert compare(ITEMS, old, new, max_broken=0).ship is True


# --- running a prompt with a fake LLM -------------------------------------

def test_run_prompt_sends_rendered_prompt_and_records_hash():
    seen = []

    def fake_llm(prompt: str) -> str:
        seen.append(prompt)
        return "billing"

    template = "Route this: {ticket}"
    record = run_prompt(template, ITEMS, fake_llm)
    assert seen == ["Route this: refund please", "Route this: app crashes", "Route this: cancel us"]
    assert record["prompt_sha256"] == prompt_sha256(template)
    assert record["outputs"] == {"a": "billing", "b": "billing", "c": "billing"}


def test_render_only_fills_the_ticket_slot():
    assert render("A {ticket} B {other}", "x") == "A x B {other}"


# --- freshness guard -----------------------------------------------------

def test_stale_outputs_are_refused(tmp_path):
    prompts, outputs = tmp_path / "prompts", tmp_path / "outputs"
    prompts.mkdir()
    outputs.mkdir()
    (prompts / "v9.txt").write_text("old prompt {ticket}")
    record = run_prompt("old prompt {ticket}", ITEMS, lambda p: "bug")
    (outputs / "v9.json").write_text(json.dumps(record))
    assert load_outputs("v9", outputs, prompts)["a"] == "bug"

    (prompts / "v9.txt").write_text("edited prompt {ticket}")
    with pytest.raises(StaleOutputsError):
        load_outputs("v9", outputs, prompts)


# --- the real lab data ---------------------------------------------------

def test_eval_set_is_balanced_and_valid():
    items = load_eval_set()
    assert len(items) == 20
    for label in LABELS:
        assert sum(item["label"] == label for item in items) == 4


def test_v2_prompt_lists_every_label():
    v2 = load_prompt("v2")
    for label in LABELS:
        assert label in v2
    assert "{ticket}" in v2 and "{ticket}" in load_prompt("v1")


def test_saved_outputs_match_the_current_prompts():
    # Fails if someone edits a prompt without re-running it.
    load_outputs("v1")
    load_outputs("v2")


def test_readme_scorecard_numbers():
    items = load_eval_set()
    result = compare(items, load_outputs("v1"), load_outputs("v2"), max_broken=1)
    assert (result.old.correct, result.old.wrong, result.old.invalid) == (8, 1, 11)
    assert (result.new.correct, result.new.wrong, result.new.invalid) == (17, 3, 0)
    assert len(result.fixed) == 10
    assert result.broken == ["t12"]
    assert result.ship is True
    # With zero tolerance for regressions, the same v2 is blocked.
    assert compare(items, load_outputs("v1"), load_outputs("v2"), max_broken=0).ship is False


def test_report_prints_the_table():
    text = report()
    assert "| v1 | 8/20 | 1 | 11 | 40% |" in text
    assert "| v2 | 17/20 | 3 | 0 | 85% |" in text
    assert "Ship v2 (more correct, at most 1 broken): yes" in text
