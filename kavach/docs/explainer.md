# Decision explainer

**Result: `POST /v1/explain` turns a fraud decision into one plain-English summary plus up to 5 reasons, and a test proves every number in the text comes from the decision itself (16 new tests, CI-checked).**

## The problem

KAVACH returns a risk score and an outcome (approve, review, decline). A bank's support agent, a customer whose payment was blocked, or an auditor cannot act on `0.87`. They need to know *why*, in words, and they need to trust that the words match the data.

## What this adds

| File | What it does |
| --- | --- |
| `app/schemas/decisions.py` | `Decision` (outcome, risk score, the signals that fired) and `ExplanationResponse` (summary, reasons, evidence) |
| `app/services/decisions.py` | An in-memory store of decisions by `transaction_id`, seeded with one demo decision `txn_demo_0001` |
| `app/services/explainer.py` | One sentence template per signal; ranks signals by contribution and fills in the observed value and threshold |
| `app/routers/v1.py` | `POST /v1/explain`: 200 with the explanation, 404 if the transaction has no decision, 422 for a bad request |

Example response (demo decision, default `max_reasons` of 3):

```json
{
  "transaction_id": "txn_demo_0001",
  "outcome": "decline",
  "risk_score": 0.87,
  "summary": "This payment was declined with a risk score of 0.87 out of 1. The biggest factor: The amount is 12.4x this customer's usual payment (we flag anything above 5x).",
  "reasons": [
    {"code": "amount_vs_average", "text": "The amount is 12.4x this customer's usual payment (we flag anything above 5x).", "evidence": {"observed": 12.4, "threshold": 5.0}, "contribution": 0.41},
    {"code": "new_account", "text": "The account is only 3 days old (we flag accounts younger than 30 days).", "evidence": {"observed": 3.0, "threshold": 30.0}, "contribution": 0.22},
    {"code": "distance_from_merchant", "text": "The customer was 1,180 km from the merchant (we flag more than 500 km).", "evidence": {"observed": 1180.0, "threshold": 500.0}, "contribution": 0.14}
  ],
  "reasons_not_shown": 1
}
```

## Run it

```bash
cd kavach
pip install -r requirements.txt
pytest -q tests/test_explain.py -v
uvicorn app.main:app --reload
curl -s -X POST localhost:8000/v1/explain -H 'content-type: application/json' \
  -d '{"transaction_id": "txn_demo_0001"}'
```

## Why it matters to a business

A blocked payment becomes a support call. If the agent can read "the amount is 12.4x this customer's usual payment" off the screen, the call is short and the customer hears a reason, not "the system said no". The same text, with its evidence, is what a regulator or the bank's risk team asks for when a decision is challenged.

## Trade-off

I used fixed templates instead of an LLM. The wording is stiffer and every new signal needs a new sentence (a test fails if one is missing), but the same decision always gets the same words, no number can be invented, and there is no model call on the request path. An LLM can rephrase later for tone, on top of these facts, not instead of them.

The store is in memory with one demo decision, so it resets on restart. That is fine until `POST /v1/score` writes real decisions; replacing it with a database only changes `app/services/decisions.py`.
