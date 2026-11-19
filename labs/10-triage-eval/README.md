# Lab 10: ticket triage eval on 50 labelled examples, and an agent with a max-iterations cap

**Result:** a keyword triage baseline puts 35 of 50 labelled tickets (70%) in the right queue, sends 12 to a human and only 3 to the wrong queue; and an agent that keeps calling tools is stopped after exactly 5 turns and escalated, instead of looping (and billing) forever.

## The problem

Two questions come up on every AI support project:

1. **"Is it good enough?"** Nobody can answer that from a demo. You need a fixed set of labelled tickets and a score you can re-run every time the prompt, model or rules change.
2. **"What if the agent gets stuck?"** An agent is a loop: the model picks a tool, sees the result, picks again. A confused model can call the same tool forever. Each turn costs money and time, and the customer waits.

## What this lab does

| File | Job |
| --- | --- |
| `tickets.json` | 50 support tickets, 10 per queue: `billing`, `account_access`, `bug`, `feature_request`, `cancellation`. |
| `triage.py` | `keyword_classifier` (rule baseline, no key) and `llm_classifier(llm)`, which wraps any LLM and forces its answer to an allowed label or `needs_human`. |
| `evaluate.py` | Accuracy, precision and recall per queue, and the list of misses. |
| `agent.py` | `run_agent(ticket, llm, tools, max_iterations=5)`: a tool loop that stops on a final answer or at the cap, and turns unknown tools, failing tools and garbage model output into structured results instead of crashes. |
| `test_triage.py`, `test_agent.py` | 26 tests. Metric maths checked by hand, the README score pinned, LLMs faked, no network. |

`python evaluate.py` (deterministic, the tests assert it):

| Queue | Precision | Recall |
| --- | --- | --- |
| billing | 82% | 90% |
| account_access | 100% | 70% |
| bug | 100% | 50% |
| feature_request | 88% | 70% |
| cancellation | 100% | 70% |

Accuracy 35/50 = 70%. Of the 15 misses, 12 are `needs_human` (no keyword matched) and 3 went to the wrong queue.

`python agent.py`:

```
well-behaved     status=done      reason=final_answer   iterations=3 tool_calls=2
stuck in a loop  status=escalated reason=max_iterations iterations=5 tool_calls=5
```

## Run it

```bash
pip install -r requirements.txt
pytest -q            # 26 tests, no network, no key
python evaluate.py   # the scorecard above
python agent.py      # the two agents above
```

## Why it matters to a business

- **The eval set is the contract.** "70% today, 65% floor" is a sentence a client can sign off on. A test fails the build if the score drops, so a prompt tweak that breaks cancellations gets caught before customers see it.
- **Precision vs recall is a business choice.** A wrong queue costs a re-route and an annoyed customer; `needs_human` costs agent time. This baseline is cautious: high precision, low recall. An LLM classifier can be scored on the exact same 50 tickets to see if it moves recall without hurting precision.
- **The iteration cap is a cost and latency ceiling.** Five turns at most means a worst-case bill and a worst-case wait you can quote. Hitting it escalates to a person with the full trail, which is what a support lead wants.

## Trade-off

The keywords were written before looking at the misses, on purpose. Tuning rules on these same 50 tickets would push the score towards 100% and mean nothing; a real project would hold back a second set for that. Fifty tickets is enough to catch big regressions, not small ones: one ticket is 2 points. The cap is blunt: a hard ticket that needs a sixth step gets escalated too, so the number should come from real traces (how many turns do good runs take?), not a guess.
