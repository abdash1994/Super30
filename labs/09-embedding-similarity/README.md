# Lab 09: cosine similarity on embeddings, and what breaks when two models are mixed

**Result:** search over 8 support articles finds the right one for 8 of 8 queries when the query and the articles are embedded by the same model, and 0 of 8 when they come from two different models with the same vector size, with no error and plausible-looking scores; a one-line model check turns that silent failure into a clear refusal.

## The problem

Retrieval (the "R" in RAG) works by turning text into a vector, an embedding, and finding the stored vectors that point in the most similar direction. The measure is cosine similarity: 1 means same direction, 0 means unrelated, -1 means opposite.

The trap: every embedding model has its own private coordinate system. A vector from model A and a vector from model B are not comparable, even when both have 1,536 numbers. This happens in real projects when a team upgrades the embedding model for new documents but keeps the old vectors, or when the query side and the indexing side are configured separately. Nothing crashes. Search just quietly starts returning the wrong documents.

## What this lab does

| File | Job |
| --- | --- |
| `similarity.py` | `cosine` (raw maths, rejects zero vectors and size mismatches), an `Embedding` that carries its model name, `safe_cosine` and `top_k` that refuse to compare different models, and `hit_rate` for top-1 accuracy. |
| `fixtures.py` | Hand-made vectors: 8 support articles and 8 queries on 8 readable axes (billing, refund, login, ...). `model-b` is a fixed rotation of the same space (same size, same internal similarities, different coordinates), which is how two real models look to each other. `model-c` is a smaller 4-number model. No model download, no network. |
| `demo.py` | Prints the table below. |
| `test_similarity.py` | 16 tests: cosine maths against hand calculations, 100% hit rate within each model, the silent mixed-model failure, the guard refusing it, and the loud failure when sizes differ. |

`python demo.py` output (deterministic, the tests assert these rows):

| Query model | Corpus model | Top-1 hit rate, no guard | With model guard |
| --- | --- | --- | --- |
| model-a | model-a | 100% | 100% |
| model-b | model-b | 100% | 100% |
| model-a | model-b | 0% | refused |
| model-b | model-a | 0% | refused |
| model-a | model-c | error: dims differ | refused |

The dangerous row is the third one. Different sizes (last row) crash immediately, which is the good outcome. Same size, different model, returns an answer every time, and it is wrong every time.

## Run it

```bash
pip install -r requirements.txt
pytest -q          # 16 tests, no network
python demo.py     # prints the table
```

## Why it matters to a business

A retrieval system that silently returns wrong documents is worse than one that is down: the assistant answers confidently from the wrong policy, and nobody notices until a customer does. Tagging every stored vector with the model that made it costs one field per row and turns a model upgrade from a silent quality collapse into a visible migration task ("re-embed 40,000 documents before switching"). It also gives you the evaluation habit: a small labelled query set and a hit rate is how you prove a new embedding model is actually better before switching.

## Trade-off

The guard trusts the model label; if someone stores a wrong label, it cannot help, so the hit-rate check on a small labelled set is still the real safety net. Refusing mixed comparisons also means a model upgrade forces a full re-embed (time and API cost) instead of a gradual rollover, unless you run two indexes side by side during the move. And the fixtures are 8-number toy vectors chosen to be readable; real embeddings have hundreds or thousands of dimensions and messier scores, but the failure is the same.
