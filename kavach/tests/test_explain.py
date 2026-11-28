"""POST /v1/explain and the template explainer behind it."""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Decision, Outcome, Signal, SignalCode
from app.services import decisions as decision_service
from app.services import explainer

client = TestClient(app)
DEMO = decision_service.DEMO_TRANSACTION_ID


def make_decision(signals, outcome=Outcome.review, score=0.6, txn="txn_test_01"):
    return Decision(transaction_id=txn, outcome=outcome, risk_score=score, signals=signals)


def test_every_signal_code_has_a_template():
    # Adding a signal without a sentence would crash the explainer.
    assert set(explainer.TEMPLATES) == set(SignalCode)


def test_every_outcome_has_words():
    assert set(explainer.OUTCOME_WORDS) == set(Outcome)


@pytest.mark.parametrize("code", list(SignalCode))
def test_reason_text_quotes_the_evidence_numbers(code):
    signal = Signal(code=code, observed=7, threshold=4, contribution=0.3)
    reason = explainer.reason_for(signal)
    assert "7" in reason.text and "4" in reason.text
    assert reason.evidence.observed == 7
    assert reason.evidence.threshold == 4


def test_reasons_are_biggest_first_and_capped():
    signals = [
        Signal(code=SignalCode.new_account, observed=3, threshold=30, contribution=0.1),
        Signal(code=SignalCode.amount_vs_average, observed=9, threshold=5, contribution=0.5),
        Signal(code=SignalCode.failed_attempts, observed=4, threshold=3, contribution=0.3),
    ]
    result = explainer.explain(make_decision(signals), max_reasons=2)
    assert [r.code for r in result.reasons] == [
        SignalCode.amount_vs_average,
        SignalCode.failed_attempts,
    ]
    assert result.reasons_not_shown == 1


def test_summary_names_outcome_score_and_top_reason():
    signals = [Signal(code=SignalCode.amount_vs_average, observed=12.4, threshold=5, contribution=0.4)]
    result = explainer.explain(make_decision(signals, Outcome.decline, 0.87))
    assert result.summary.startswith("This payment was declined with a risk score of 0.87")
    assert result.reasons[0].text in result.summary


def test_no_signals_says_so():
    result = explainer.explain(make_decision([], Outcome.approve, 0.05))
    assert result.reasons == []
    assert "No risk signals fired." in result.summary


def test_every_number_in_the_text_comes_from_the_decision():
    # The explainer must never invent a figure.
    decision = decision_service.demo_decision()
    result = explainer.explain(decision, max_reasons=5)
    allowed = {f"{decision.risk_score:.2f}", "1"}  # "1" is the fixed "out of 1"
    for s in decision.signals:
        for v in (s.observed, s.threshold):
            allowed.update({f"{v:g}", f"{v:.0f}", f"{v:,.0f}"})
    text = " ".join([result.summary] + [r.text for r in result.reasons])
    found = set(re.findall(r"\d[\d,]*(?:\.\d+)?", text))
    assert found <= allowed, found - allowed


def test_same_decision_same_words():
    d = decision_service.demo_decision()
    assert explainer.explain(d) == explainer.explain(d)


def test_explain_endpoint_returns_demo_decision():
    response = client.post("/v1/explain", json={"transaction_id": DEMO})
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "decline"
    assert len(body["reasons"]) == 3  # default max_reasons
    assert body["reasons_not_shown"] == 1
    assert body["reasons"][0]["code"] == "amount_vs_average"
    assert body["reasons"][0]["evidence"] == {"observed": 12.4, "threshold": 5.0}


def test_explain_endpoint_respects_max_reasons():
    response = client.post("/v1/explain", json={"transaction_id": DEMO, "max_reasons": 1})
    assert len(response.json()["reasons"]) == 1


def test_unknown_transaction_is_404_with_message():
    response = client.post("/v1/explain", json={"transaction_id": "txn_missing_99"})
    assert response.status_code == 404
    assert "txn_missing_99" in response.json()["detail"]


def test_bad_request_is_422():
    response = client.post("/v1/explain", json={"transaction_id": DEMO, "max_reasons": 9})
    assert response.status_code == 422


def test_explain_route_is_versioned():
    assert client.post("/explain", json={"transaction_id": DEMO}).status_code == 404
    assert "/v1/explain" in client.get("/openapi.json").json()["paths"]
