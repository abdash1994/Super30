"""Decision and explanation models.

A Decision is what the scorer produced for one transaction: the outcome, the
risk score and the signals that pushed the score up. An Explanation is the
same decision written for a person: one plain-English summary, then one
reason per signal with the evidence (what we saw vs. the line we draw).
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.requests import ID_PATTERN


class Outcome(str, Enum):
    approve = "approve"
    review = "review"
    decline = "decline"


class SignalCode(str, Enum):
    """Every signal the scorer can raise. Each one has a sentence template."""

    amount_vs_average = "amount_vs_average"
    new_account = "new_account"
    failed_attempts = "failed_attempts"
    distance_from_merchant = "distance_from_merchant"


class Signal(BaseModel):
    """One rule that fired, with the number we saw and the line it crossed."""

    model_config = ConfigDict(extra="forbid")

    code: SignalCode
    observed: float = Field(ge=0)
    threshold: float = Field(ge=0)
    contribution: float = Field(ge=0, le=1)  # share of the risk score


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=4, max_length=64, pattern=ID_PATTERN)
    outcome: Outcome
    risk_score: float = Field(ge=0, le=1)
    signals: list[Signal] = Field(default_factory=list)


class Evidence(BaseModel):
    observed: float
    threshold: float


class Reason(BaseModel):
    code: SignalCode
    text: str
    evidence: Evidence
    contribution: float


class ExplanationResponse(BaseModel):
    """Body returned by POST /v1/explain."""

    transaction_id: str
    outcome: Outcome
    risk_score: float
    summary: str
    reasons: list[Reason]
    reasons_not_shown: int
