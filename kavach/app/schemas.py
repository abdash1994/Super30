"""Request models for the KAVACH API.

KAVACH scores a payment transaction for fraud risk before it is approved.
These models are the contract for what a client may send. Anything that
breaks a rule here is rejected with a 422 before it reaches the model, the
cache or the audit log.

Rules are deliberately strict on day one: under the versioning policy,
tightening validation later is a breaking change, while loosening it is not.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

# IDs: letters, digits, "_" and "-" only, so they are safe in logs, cache keys
# and URLs. Length bounds stop empty strings and pasted blobs.
ID_PATTERN = r"^[A-Za-z0-9_-]+$"

# How far into the future a transaction_time may be, to allow for clock skew
# between the client's servers and ours.
MAX_CLOCK_SKEW = timedelta(minutes=5)


class StrictModel(BaseModel):
    """Base for every request: unknown fields are an error, not ignored.

    A typo like "amout" would otherwise be silently dropped and the request
    scored with a missing value.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MerchantCategory(str, Enum):
    travel = "travel"
    gaming = "gaming"
    electronics = "electronics"
    quick_commerce = "quick_commerce"
    grocery = "grocery"
    fuel = "fuel"
    utilities = "utilities"
    other = "other"


class PaymentChannel(str, Enum):
    upi = "upi"
    card = "card"
    net_banking = "net_banking"
    wallet = "wallet"


class Location(StrictModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    city: str = Field(min_length=1, max_length=80)


class ScoreRequest(StrictModel):
    """One transaction to score. Body of POST /v1/score."""

    transaction_id: str = Field(min_length=4, max_length=64, pattern=ID_PATTERN)
    customer_id: str = Field(min_length=4, max_length=64, pattern=ID_PATTERN)
    device_id: str = Field(min_length=4, max_length=64, pattern=ID_PATTERN)

    # Money is Decimal, never float: 0.1 + 0.2 must equal 0.3 in rupees.
    amount_inr: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    merchant_category: MerchantCategory
    payment_channel: PaymentChannel
    transaction_time: AwareDatetime  # must carry a timezone, e.g. +05:30

    customer_age: int = Field(ge=18, le=120)
    account_age_days: int = Field(ge=0, le=36500)
    previous_transactions: int = Field(ge=0)
    avg_transaction_value_inr: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    failed_transactions: int = Field(ge=0)

    customer_location: Location
    merchant_location: Location

    @field_validator("transaction_time")
    @classmethod
    def not_in_future(cls, value: datetime) -> datetime:
        if value > datetime.now(timezone.utc) + MAX_CLOCK_SKEW:
            raise ValueError("transaction_time is in the future")
        return value


class ExplainRequest(StrictModel):
    """Ask why a scored transaction got its decision. Body of POST /v1/explain."""

    transaction_id: str = Field(min_length=4, max_length=64, pattern=ID_PATTERN)
    max_reasons: int = Field(default=3, ge=1, le=5)
