from collections import Counter

import pytest

from evaluate import TICKETS, evaluate
from triage import LABELS, NEEDS_HUMAN, keyword_classifier, llm_classifier

# --- the labelled set itself ---------------------------------------------


def test_dataset_has_50_tickets_10_per_label_with_unique_ids():
    assert len(TICKETS) == 50
    assert len({t["id"] for t in TICKETS}) == 50
    assert Counter(t["label"] for t in TICKETS) == {label: 10 for label in LABELS}


# --- metric maths on a tiny hand-checked set -----------------------------

TINY = [
    {"id": 1, "text": "a", "label": "billing"},
    {"id": 2, "text": "b", "label": "billing"},
    {"id": 3, "text": "c", "label": "bug"},
    {"id": 4, "text": "d", "label": "bug"},
]


def test_metrics_match_hand_calculation():
    answers = {"a": "billing", "b": "bug", "c": "bug", "d": NEEDS_HUMAN}
    report = evaluate(lambda text: answers[text], TINY)
    assert (report.correct, report.total) == (2, 4)
    assert report.accuracy == 0.5
    assert report.needs_human == 1
    assert report.precision("billing") == 1.0  # 1 predicted billing, 1 right
    assert report.recall("billing") == 0.5  # 2 real billing, 1 found
    assert report.precision("bug") == 0.5  # 2 predicted bug, 1 right
    assert report.recall("bug") == 0.5
    assert report.misses == [(2, "billing", "bug"), (4, "bug", NEEDS_HUMAN)]


def test_perfect_classifier_scores_100_percent_on_the_real_set():
    gold = {t["text"]: t["label"] for t in TICKETS}
    report = evaluate(lambda text: gold[text])
    assert report.accuracy == 1.0
    assert all(report.precision(l) == 1.0 and report.recall(l) == 1.0 for l in LABELS)


# --- keyword baseline: the number in the README --------------------------


def test_keyword_baseline_score_is_what_the_readme_says():
    report = evaluate(keyword_classifier)
    assert report.correct == 35  # 70%: update README.md if this changes
    assert report.needs_human == 12
    assert len(report.misses) - report.needs_human == 3  # sent to the wrong queue


def test_keyword_baseline_never_drops_below_the_release_floor():
    assert evaluate(keyword_classifier).accuracy >= 0.65


@pytest.mark.parametrize(
    "text, label",
    [
        ("Please cancel my plan", "cancellation"),
        ("I forgot my password", "account_access"),
        ("Refund my last payment", "billing"),
        ("The page shows an error", "bug"),
        ("Feature idea: offline mode", "feature_request"),
        ("Hello there", NEEDS_HUMAN),
    ],
)
def test_keyword_classifier_examples(text, label):
    assert keyword_classifier(text) == label


def test_tie_goes_to_cancellation():
    # "cancel" scores 3 and "login" scores 3: a tie, broken towards cancellation.
    assert keyword_classifier("cancel, the login") == "cancellation"


# --- LLM classifier (fake model, no network) -----------------------------


def test_llm_classifier_accepts_allowed_labels_with_noise():
    classify = llm_classifier(lambda prompt: "  Billing.\n")
    assert classify("charged twice") == "billing"


def test_llm_classifier_sends_unknown_answers_to_a_human():
    classify = llm_classifier(lambda prompt: "refunds team")
    assert classify("charged twice") == NEEDS_HUMAN
    assert llm_classifier(lambda prompt: None)("x") == NEEDS_HUMAN


def test_llm_classifier_prompt_contains_ticket_and_every_label():
    seen = []
    llm_classifier(lambda prompt: seen.append(prompt) or "bug")("App crashed")
    assert "App crashed" in seen[0]
    assert all(label in seen[0] for label in LABELS)


def test_fake_llm_that_knows_the_answers_scores_100_percent():
    gold = {t["text"]: t["label"] for t in TICKETS}
    fake = lambda prompt: gold[prompt.split("Ticket: ", 1)[1]]
    assert evaluate(llm_classifier(fake)).accuracy == 1.0
