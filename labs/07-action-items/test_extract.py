import json

import pytest

import evaluate as ev
from baseline import baseline_llm, extract_items
from extract import UNASSIGNED, ExtractionError, build_prompt, check, extract, guard_owners

ATTENDEES = ["Priya", "Ravi"]
GOOD = json.dumps({"action_items": [{"task": "Fix the login bug", "owner": "Ravi", "due": "Friday"}]})


class FakeLLM:
    """Returns canned replies in order and remembers every prompt it saw."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0)


# --- the extraction pipeline ------------------------------------------------

def test_valid_reply_first_time():
    llm = FakeLLM(GOOD)
    result = extract("Ravi: I'll fix the login bug by Friday.", ATTENDEES, llm)
    assert result.action_items == [{"task": "Fix the login bug", "owner": "Ravi", "due": "Friday"}]
    assert result.attempts == 1
    assert result.warnings == []


def test_prompt_carries_schema_attendees_and_unassigned_rule():
    prompt = build_prompt("Priya: hi", ATTENDEES)
    assert '"action_items"' in prompt
    assert "Priya, Ravi" in prompt
    assert f'"{UNASSIGNED}"' in prompt and "Never guess an owner" in prompt


def test_not_json_gets_one_retry_with_the_error():
    llm = FakeLLM("Sure! Here are the action items:", GOOD)
    result = extract("...", ATTENDEES, llm)
    assert result.attempts == 2
    assert "not valid JSON" in llm.prompts[1]
    assert "previous reply was rejected" in llm.prompts[1]


def test_schema_violation_twice_raises():
    missing_owner = json.dumps({"action_items": [{"task": "Do it", "due": None}]})
    llm = FakeLLM(missing_owner, missing_owner)
    with pytest.raises(ExtractionError, match="'owner' is a required property"):
        extract("...", ATTENDEES, llm)
    assert len(llm.prompts) == 2


@pytest.mark.parametrize(
    "data",
    [
        [],  # root must be an object
        {"items": []},  # wrong key
        {"action_items": [{"task": "Do it", "owner": "", "due": None}]},  # empty owner
        {"action_items": [{"task": "Do it", "owner": "Ravi", "due": 5}]},  # due not text/null
        {"action_items": [{"task": "Do it", "owner": "Ravi", "due": None, "priority": 1}]},  # extra field
    ],
)
def test_schema_rejects_bad_shapes(data):
    parsed, error = check(json.dumps(data))
    assert parsed is None and error.startswith("schema error")


def test_empty_list_is_a_valid_answer():
    parsed, error = check('{"action_items": []}')
    assert parsed == {"action_items": []} and error is None


def test_outsider_owner_becomes_unassigned_with_warning():
    items = [{"task": "Sign the contract", "owner": "Legal team", "due": None}]
    cleaned, warnings = guard_owners(items, ATTENDEES)
    assert cleaned[0]["owner"] == UNASSIGNED
    assert "Legal team" in warnings[0]


def test_owner_case_is_normalised():
    items = [
        {"task": "A task", "owner": "ravi", "due": None},
        {"task": "B task", "owner": "Unassigned", "due": None},
    ]
    cleaned, warnings = guard_owners(items, ATTENDEES)
    assert [i["owner"] for i in cleaned] == ["Ravi", UNASSIGNED]
    assert warnings == []


# --- the rule-based baseline ------------------------------------------------

def test_baseline_phrasings():
    transcript = (
        "Priya: I'll send the deck by Monday. Ravi, can you book the room?\n"
        "Ravi: Someone needs to update the wiki."
    )
    assert extract_items(transcript, ATTENDEES) == [
        {"task": "Send the deck", "owner": "Priya", "due": "Monday"},
        {"task": "Book the room", "owner": "Ravi", "due": None},
        {"task": "Update the wiki", "owner": UNASSIGNED, "due": None},
    ]


def test_baseline_output_passes_the_schema():
    llm = baseline_llm("Priya: I'll do the thing.", ATTENDEES)
    assert check(llm("ignored"))[1] is None


# --- the evaluation -----------------------------------------------------------

def test_there_are_ten_labelled_samples():
    assert len(ev.SAMPLES) == 10
    assert sum(g["owner"] == UNASSIGNED for s in ev.SAMPLES for g in s["expected"]) >= 3


def test_match_needs_all_keywords_and_matches_once():
    expected = [{"keywords": ["login", "bug"]}, {"keywords": ["login", "bug"]}]
    predicted = [{"task": "Fix the login bug"}, {"task": "Fix login"}]
    assert len(ev.match(predicted, expected)) == 1


def test_baseline_score_is_what_the_readme_says():
    score = ev.evaluate(lambda s: baseline_llm(s["transcript"], s["attendees"]))
    assert (score.schema_valid, score.samples) == (10, 10)
    assert (score.matched, score.predicted, score.expected) == (15, 16, 18)
    assert score.owner_correct == 15
    assert score.due_correct == 13
    assert (score.unassigned_correct, score.unassigned_expected) == (4, 4)


def test_a_model_that_never_returns_json_scores_zero():
    score = ev.evaluate(lambda s: (lambda prompt: "I could not find any."))
    assert score.schema_valid == 0
    assert score.matched == 0 and score.recall == 0


def test_cli_baseline(capsys):
    assert ev.main([]) == 0
    assert "Recall               : 15/18 = 83%" in capsys.readouterr().out


def test_cli_live_uses_the_real_model_function(monkeypatch, capsys):
    calls = []

    def fake_live(prompt):
        calls.append(prompt)
        return '{"action_items": []}'

    monkeypatch.setattr(ev, "anthropic_llm", fake_live)
    assert ev.main(["--live"]) == 0
    assert len(calls) == 10
    assert "Schema-valid replies : 10/10" in capsys.readouterr().out
