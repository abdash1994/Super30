"""Turn a fraud decision into plain English, with its evidence.

Sentences come from fixed templates, not an LLM: the same decision always
gets the same words, every number in the text is a number from the
decision, and an auditor can read the template that produced it.
"""

from app.schemas import (
    Decision,
    Evidence,
    ExplanationResponse,
    Outcome,
    Reason,
    Signal,
    SignalCode,
)

# One sentence per signal. {observed} and {threshold} are filled from the
# signal; nothing else goes in.
TEMPLATES: dict[SignalCode, str] = {
    SignalCode.amount_vs_average: (
        "The amount is {observed:g}x this customer's usual payment "
        "(we flag anything above {threshold:g}x)."
    ),
    SignalCode.new_account: (
        "The account is only {observed:.0f} days old "
        "(we flag accounts younger than {threshold:.0f} days)."
    ),
    SignalCode.failed_attempts: (
        "There were {observed:.0f} failed payment attempts before this one "
        "(we flag {threshold:.0f} or more)."
    ),
    SignalCode.distance_from_merchant: (
        "The customer was {observed:,.0f} km from the merchant "
        "(we flag more than {threshold:,.0f} km)."
    ),
}

OUTCOME_WORDS: dict[Outcome, str] = {
    Outcome.approve: "approved",
    Outcome.review: "held for manual review",
    Outcome.decline: "declined",
}


def reason_for(signal: Signal) -> Reason:
    text = TEMPLATES[signal.code].format(
        observed=signal.observed, threshold=signal.threshold
    )
    return Reason(
        code=signal.code,
        text=text,
        evidence=Evidence(observed=signal.observed, threshold=signal.threshold),
        contribution=signal.contribution,
    )


def explain(decision: Decision, max_reasons: int = 3) -> ExplanationResponse:
    """Biggest reasons first, capped at max_reasons."""
    ranked = sorted(decision.signals, key=lambda s: s.contribution, reverse=True)
    reasons = [reason_for(s) for s in ranked[:max_reasons]]

    summary = (
        f"This payment was {OUTCOME_WORDS[decision.outcome]} "
        f"with a risk score of {decision.risk_score:.2f} out of 1."
    )
    if reasons:
        summary += f" The biggest factor: {reasons[0].text}"
    else:
        summary += " No risk signals fired."

    return ExplanationResponse(
        transaction_id=decision.transaction_id,
        outcome=decision.outcome,
        risk_score=decision.risk_score,
        summary=summary,
        reasons=reasons,
        reasons_not_shown=len(ranked) - len(reasons),
    )
