# Lab 13: prompt v1 vs v2, scored on the same 20-ticket eval set

**Result:** on the same 20 labelled tickets, prompt v2 gets 17 right (85%) against v1's 8 (40%); v1's real problem was 11 answers code could not parse, not wrong answers; and the item-by-item diff shows v2 fixed 10 tickets but broke 1 (t12), which a plain accuracy number would hide.

## The problem

"I tweaked the prompt and it feels better" is how most prompt changes ship. Three things go wrong:

1. **Different examples each time.** If v1 was tried on Monday's tickets and v2 on Tuesday's, the scores are not comparable.
2. **The average hides regressions.** v2 can win overall and still break the one ticket type a client cares about.
3. **The score drifts from the prompt.** Someone edits the prompt after the eval ran, and the old number keeps getting quoted.

## What this lab does

| File | Job |
| --- | --- |
| `eval_set.json` | 20 support tickets, 4 per queue: `billing`, `account_access`, `bug`, `feature_request`, `cancellation`. |
| `prompts/v1.txt` | The "first try" prompt: just asks which team should handle it. |
| `prompts/v2.txt` | Lists the five queues with one-line definitions, a tie-break rule for cancellations, and "reply with the queue name only". |
| `outputs/v1.json`, `outputs/v2.json` | The answers for each prompt, saved with the SHA-256 of the prompt that produced them. These are hand-written to mimic typical model behaviour so the lab runs with no key; `run_prompt()` makes real ones. |
| `promptlab.py` | `run_prompt` (any `llm(prompt) -> text`), a strict `parse_label`, `score`, `compare` (fixed / broken per item and a ship rule), and `load_outputs`, which refuses answers made with an older version of the prompt. |
| `compare.py` | Prints the scorecard below. |
| `test_promptlab.py` | 24 tests. Fake LLM, no network; the README numbers are pinned. |

`python compare.py`:

| Prompt | Correct | Wrong label | Unparseable | Accuracy |
| --- | --- | --- | --- | --- |
| v1 | 8/20 | 1 | 11 | 40% |
| v2 | 17/20 | 3 | 0 | 85% |

```
Fixed by v2 (10): t03, t05, t06, t07, t11, t13, t14, t15, t16, t19
Broken by v2 (1): t12
Ship v2 (more correct, at most 1 broken): yes
```

v1 answers like "Account support" or "The billing team should handle this." are not wrong, but nothing downstream can route them. v2 broke t12 ("dates show up a day early for our Sydney team"): it now calls a time-zone bug a feature request. Allow 0 regressions and the same v2 is blocked.

## Run it

```bash
pip install -r requirements.txt
pytest -q            # 24 tests, no network, no key
python compare.py    # the scorecard above
```

To score a real model, pass your client as `llm` to `run_prompt(load_prompt("v2"), load_eval_set(), llm)` and save the result to `outputs/v2.json`.

## Why it matters to a business

- **Same set, every time.** A fixed eval set turns "v2 feels better" into "v2 goes from 8 to 17 out of 20". That is a number a client can approve, and the same set catches the next change.
- **Format is half the battle.** Most of v1's misses were answers a system cannot use. Listing allowed labels and forcing a one-word reply is often the cheapest win available.
- **Read the diff, not just the average.** The ship rule asks two questions: is it better overall, and how many tickets did it break? The broken list is what you show the client before going live.
- **Scores are tied to the prompt.** The saved hash means an edited prompt cannot keep its old score; CI fails until it is re-run.

## Trade-off

Twenty tickets is small: one ticket is 5 points, so this catches big changes (40% to 85%), not small ones. The strict parser is harsh by design; a lenient one (fuzzy matching "Account Access") would flatter v1 but hide a real integration bug. The answers here are hand-written stand-ins, so the numbers show the method, not how any particular model performs; the real numbers come from one `run_prompt` call per version, which costs 20 API calls each.
