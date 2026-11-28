"""Where decisions are kept so they can be explained later.

In-memory for now. POST /v1/score will write here once it lands; until then
the store starts with one clearly labelled demo decision so the endpoint can
be tried from /docs. Swapping this for a database only changes this file.
"""

from app.schemas import Decision, Outcome, Signal, SignalCode

DEMO_TRANSACTION_ID = "txn_demo_0001"


def demo_decision() -> Decision:
    """A made-up declined payment, used only for trying the API by hand."""
    return Decision(
        transaction_id=DEMO_TRANSACTION_ID,
        outcome=Outcome.decline,
        risk_score=0.87,
        signals=[
            Signal(code=SignalCode.amount_vs_average, observed=12.4, threshold=5, contribution=0.41),
            Signal(code=SignalCode.new_account, observed=3, threshold=30, contribution=0.22),
            Signal(code=SignalCode.distance_from_merchant, observed=1180, threshold=500, contribution=0.14),
            Signal(code=SignalCode.failed_attempts, observed=4, threshold=3, contribution=0.10),
        ],
    )


class DecisionStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Decision] = {}

    def save(self, decision: Decision) -> None:
        self._by_id[decision.transaction_id] = decision

    def get(self, transaction_id: str) -> Decision | None:
        return self._by_id.get(transaction_id)


store = DecisionStore()
store.save(demo_decision())
