"""Every rule in app/schemas.py has a test that proves a bad value is rejected,
and that it is rejected for the right field and the right reason."""

import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas import ExplainRequest, ScoreRequest

IST = timezone(timedelta(hours=5, minutes=30))

VALID = {
    "transaction_id": "TXN-0001",
    "customer_id": "CUST-0042",
    "device_id": "DEV-ab12",
    "amount_inr": "3063.54",
    "merchant_category": "quick_commerce",
    "payment_channel": "net_banking",
    "transaction_time": "2026-11-01T14:05:00+05:30",
    "customer_age": 77,
    "account_age_days": 1200,
    "previous_transactions": 6,
    "avg_transaction_value_inr": "6600.00",
    "failed_transactions": 0,
    "customer_location": {"latitude": 26.91, "longitude": 75.79, "city": "Jaipur"},
    "merchant_location": {"latitude": 26.92, "longitude": 75.82, "city": "Jaipur"},
}


_REMOVE = object()  # sentinel: delete the field instead of setting it


def payload(path, value):
    """VALID with one field changed. path is a tuple; _REMOVE deletes it."""
    data = copy.deepcopy(VALID)
    target = data
    for key in path[:-1]:
        target = target[key]
    if value is _REMOVE:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return data


# ---------- accepted ----------


def test_valid_request_is_accepted():
    req = ScoreRequest(**VALID)
    assert req.amount_inr == Decimal("3063.54")
    assert req.merchant_category.value == "quick_commerce"
    assert req.transaction_time.utcoffset() == timedelta(hours=5, minutes=30)


def test_whitespace_around_ids_is_stripped():
    req = ScoreRequest(**payload(("transaction_id",), "  TXN-0001  "))
    assert req.transaction_id == "TXN-0001"


def test_boundary_values_are_accepted():
    data = payload(("customer_age",), 18)
    data["amount_inr"] = "0.01"
    data["account_age_days"] = 0
    data["customer_location"]["latitude"] = -90
    data["merchant_location"]["longitude"] = 180
    ScoreRequest(**data)


def test_explain_defaults_to_three_reasons():
    assert ExplainRequest(transaction_id="TXN-0001").max_reasons == 3


# ---------- rejected: one case per rule ----------

NOW = datetime.now(timezone.utc)

REJECTED = [
    # (case id, field path, bad value, expected pydantic error type)
    ("missing transaction_id", ("transaction_id",), _REMOVE, "missing"),
    ("transaction_id too short", ("transaction_id",), "T1", "string_too_short"),
    ("transaction_id too long", ("transaction_id",), "T" * 65, "string_too_long"),
    ("transaction_id bad chars", ("transaction_id",), "TXN 0001;DROP", "string_pattern_mismatch"),
    ("customer_id bad chars", ("customer_id",), "cust/42", "string_pattern_mismatch"),
    ("device_id empty", ("device_id",), "", "string_too_short"),
    ("amount zero", ("amount_inr",), "0", "greater_than"),
    ("amount negative", ("amount_inr",), "-10.00", "greater_than"),
    ("amount three decimals", ("amount_inr",), "10.005", "decimal_max_places"),
    ("amount too many digits", ("amount_inr",), "12345678901.00", "decimal_whole_digits"),
    ("amount not a number", ("amount_inr",), "ten", "decimal_parsing"),
    ("unknown merchant category", ("merchant_category",), "casino", "enum"),
    ("unknown payment channel", ("payment_channel",), "cheque", "enum"),
    ("time without timezone", ("transaction_time",), "2026-11-01T14:05:00", "timezone_aware"),
    ("time in the future", ("transaction_time",), (NOW + timedelta(hours=1)).isoformat(), "value_error"),
    ("time not a date", ("transaction_time",), "yesterday", "datetime_from_date_parsing"),
    ("customer under 18", ("customer_age",), 17, "greater_than_equal"),
    ("customer over 120", ("customer_age",), 121, "less_than_equal"),
    ("customer age not int", ("customer_age",), "old", "int_parsing"),
    ("account age negative", ("account_age_days",), -1, "greater_than_equal"),
    ("account age over 100 years", ("account_age_days",), 36501, "less_than_equal"),
    ("previous transactions negative", ("previous_transactions",), -1, "greater_than_equal"),
    ("avg value negative", ("avg_transaction_value_inr",), "-1.00", "greater_than_equal"),
    ("failed transactions negative", ("failed_transactions",), -3, "greater_than_equal"),
    ("latitude over 90", ("customer_location", "latitude"), 91, "less_than_equal"),
    ("latitude under -90", ("customer_location", "latitude"), -91, "greater_than_equal"),
    ("longitude over 180", ("merchant_location", "longitude"), 181, "less_than_equal"),
    ("city blank", ("merchant_location", "city"), "   ", "string_too_short"),
    ("missing location", ("customer_location",), _REMOVE, "missing"),
    ("unknown field (typo)", ("amout",), "100.00", "extra_forbidden"),
    ("unknown field in location", ("customer_location", "pincode"), "302001", "extra_forbidden"),
]


@pytest.mark.parametrize(
    "path, value, error_type",
    [case[1:] for case in REJECTED],
    ids=[case[0] for case in REJECTED],
)
def test_bad_value_is_rejected_for_the_right_reason(path, value, error_type):
    with pytest.raises(ValidationError) as exc_info:
        ScoreRequest(**payload(path, value))

    errors = exc_info.value.errors()
    assert len(errors) == 1, errors  # only the field we broke
    assert errors[0]["loc"] == path
    assert errors[0]["type"] == error_type


@pytest.mark.parametrize(
    "data, loc, error_type",
    [
        ({}, ("transaction_id",), "missing"),
        ({"transaction_id": "TXN-0001", "max_reasons": 0}, ("max_reasons",), "greater_than_equal"),
        ({"transaction_id": "TXN-0001", "max_reasons": 6}, ("max_reasons",), "less_than_equal"),
        ({"transaction_id": "TXN-0001", "verbose": True}, ("verbose",), "extra_forbidden"),
    ],
    ids=["missing id", "zero reasons", "too many reasons", "unknown field"],
)
def test_explain_request_rejections(data, loc, error_type):
    with pytest.raises(ValidationError) as exc_info:
        ExplainRequest(**data)
    errors = exc_info.value.errors()
    assert len(errors) == 1, errors
    assert errors[0]["loc"] == loc
    assert errors[0]["type"] == error_type


def test_every_constrained_field_has_a_rejection_test():
    """Guard rail: a new field on ScoreRequest needs a rejection case here."""
    tested = {case[1][0] for case in REJECTED}
    assert set(ScoreRequest.model_fields) <= tested


# ---------- what a client sees over HTTP ----------


def test_fastapi_returns_422_with_the_failing_field():
    app = FastAPI()

    @app.post("/v1/score")
    def score(req: ScoreRequest) -> dict:
        return {"transaction_id": req.transaction_id}

    client = TestClient(app)
    assert client.post("/v1/score", json=VALID).status_code == 200

    response = client.post("/v1/score", json=payload(("customer_age",), 12))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "customer_age"]
