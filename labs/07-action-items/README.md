# Lab 07: meeting transcript to action items, as schema-checked JSON

**Result:** a transcript goes in, a list of `{task, owner, due}` comes out that must match a JSON Schema (one retry, then a clear error), owners outside the meeting become `"unassigned"`, and a 10-sample labelled evaluation scores it; the rule-based baseline gets 94% precision and 83% recall, checked by CI.

## The problem

"Can the AI pull the action items out of our meetings?" is one of the first things a client asks for. The demo is easy; the production version breaks in three quiet ways:

1. **The reply is not data.** The model answers "Sure! Here are the action items:" or drops a field, and the code that writes tasks into Jira crashes, or worse, writes half a task.
2. **The model invents owners.** Asked "who owns this?", a model would rather guess a name than say nobody does. A task assigned to someone who never agreed to it is worse than no task.
3. **Nobody knows if it is any good.** Without labelled examples, "it looks right" is the only quality bar, and a prompt change can make it worse without anyone noticing.

## What this lab does

```
transcript -> prompt (with the schema) -> model -> json.loads -> schema check -> owner guard -> action items
                                            ^                         |
                                            +---- one retry, with ----+
                                                  the exact error
```

| File | Job |
| --- | --- |
| `schema.json` | The contract: `action_items` is a list of `{task, owner, due}`, no extra fields, `due` is text or `null`. |
| `extract.py` | Builds the prompt, validates the reply with `jsonschema`, retries once with the error fed back, then raises `ExtractionError`. The owner guard swaps any name that was not an attendee for `"unassigned"` and records a warning. |
| `baseline.py` | A rule-based stand-in for the LLM ("I'll ...", "Ravi, can you ...", "someone needs to ..."), so the evaluation runs in CI with no key. It is the floor a real model has to beat. |
| `samples.json` | 10 labelled transcripts, including traps: a meeting with no actions, an owner implied but not stated, a task already done, a vague "maybe at some point", two tasks in one sentence, and four tasks nobody took. |
| `evaluate.py` | Scores any model on the 10 samples: schema-valid replies, precision, recall, owner accuracy, due dates and whether "unassigned" survived. |

Baseline score (asserted exactly in `test_baseline_score_is_what_the_readme_says`, so CI fails if this table goes stale):

| Metric | Baseline |
| --- | --- |
| Schema-valid replies | 10/10 |
| Precision (items found that were real) | 15/16 = 94% |
| Recall (real items found) | 15/18 = 83% |
| Owner correct (of matched items) | 15/15 = 100% |
| Due date correct (of matched items) | 13/15 |
| "unassigned" kept as unassigned | 4/4 |

What it misses, which is where an LLM should earn its cost: "Let's have Dev own the pricing slide" (implied owner), "I can take the vendor call" (soft commitment), the second task in "I'll clean up the test data and I'll rerun the evaluation", and "today" as a deadline. Its one false positive is "I'll think about the colour scheme", which is not a task.

## Run it

```bash
pip install -r requirements.txt
pytest -q                        # 20 tests, no key, no network

python evaluate.py               # baseline score on the 10 samples

# Optional, with a real model (costs a few cents):
export ANTHROPIC_API_KEY=...     # never commit this
export LAB07_MODEL=...           # a model id your key can use
python evaluate.py --live
```

## Why it matters to a business

The schema is what turns an AI feature into something other systems can trust: the task tracker, the reminder email and the weekly report all read the same three fields, and bad output stops at the door instead of spreading. Allowing "unassigned" protects people: the meeting's real gap ("nobody owns the audit-log check") is surfaced instead of being hidden behind a made-up owner. And the 10-sample evaluation gives the client a number to agree on before launch ("recall must be above 90% on these samples"), so switching models or editing the prompt becomes a measured decision, not a vibe.

## Trade-off

Ten samples is enough to catch regressions and start a conversation, not enough to prove quality; a real engagement would label 50 to 100 transcripts from the client's own meetings. Matching by keywords is simple and explainable but generous (any task containing "contract" matches). The schema check runs after the model replies, so a bad reply costs a second call; providers' built-in structured-output modes can enforce the shape during generation instead, but then the lab would depend on one vendor's feature. The owner guard only knows names, so "Ravi" and "Ravi K." count as different people.
