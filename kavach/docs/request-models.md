# Request models

**Result: every field a client sends to KAVACH has a rule, and every rule has a test that proves a bad value gets a 422 naming the exact field (35 rejection cases, CI-checked).**

## The problem

KAVACH scores a payment for fraud before it is approved. If a client sends an amount of `-500`, a time with no timezone, or a typo like `amout`, a loose API either crashes later or, worse, scores the transaction with a wrong or missing value and logs a confident decision. In fraud, a silent wrong answer costs more than a loud rejection.

## What this adds

`app/schemas.py` defines the request contract with Pydantic `Field` constraints:

| Model | Used for | Key rules |
| --- | --- | --- |
| `ScoreRequest` | `POST /v1/score` (endpoint wired next) | IDs 4 to 64 chars of `A-Z a-z 0-9 _ -`; `amount_inr` is a Decimal above 0 with at most 2 decimals; category and channel from fixed lists; `transaction_time` must carry a timezone and not be more than 5 minutes in the future; customer age 18 to 120; counts never negative |
| `Location` | customer and merchant location | latitude -90 to 90, longitude -180 to 180, city not blank |
| `ExplainRequest` | `POST /v1/explain` | transaction ID, `max_reasons` 1 to 5 (default 3) |

All models reject unknown fields and strip spaces around text.

`tests/test_schemas.py` has one parametrized case per rule (31 for scoring, 4 for explain). Each case breaks exactly one field and checks three things: it is rejected, only that field is reported, and the reason is the expected one. A guard test fails if someone adds a field to `ScoreRequest` without a rejection case. One more test runs the model behind a real FastAPI route and checks the client gets a 422 with `["body", "customer_age"]`.

## Run it

```bash
cd kavach
pip install -r requirements.txt
pytest -q tests/test_schemas.py -v   # one line per rejected case
```

## Why it matters to a business

The bank's integration team gets a precise error ("`amount_inr`: at most 2 decimal places") on their first test call, instead of a support ticket a week later. Our model, cache and audit log only ever see clean data, so a fraud decision can be defended to an auditor. Money as `Decimal` means paise never drift through float rounding.

## Trade-off

I made validation strict on day one: unknown fields are rejected, not ignored, and limits are tight. That will annoy a client who sends extra fields, and some limits (like age 18 to 120) are my assumptions to confirm with PayVista. I accepted that because under our versioning policy, loosening a rule later is additive and safe, while tightening one later is a breaking change that needs `/v2`.
