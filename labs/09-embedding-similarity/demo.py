"""Print what happens to search quality when query and corpus models differ."""
from __future__ import annotations

import fixtures
from similarity import EmbeddingMismatchError, hit_rate

SETUPS = [
    ("model-a", "model-a"),
    ("model-b", "model-b"),
    ("model-a", "model-b"),
    ("model-b", "model-a"),
    ("model-a", "model-c"),
]


def rows() -> list[tuple[str, str, str, str]]:
    out = []
    for q_model, c_model in SETUPS:
        qs, docs = fixtures.queries(q_model), fixtures.corpus(c_model)
        try:
            unguarded = f"{hit_rate(qs, docs, check=False):.0%}"
        except EmbeddingMismatchError:
            unguarded = "error: dims differ"
        try:
            guarded = f"{hit_rate(qs, docs, check=True):.0%}"
        except EmbeddingMismatchError:
            guarded = "refused"
        out.append((q_model, c_model, unguarded, guarded))
    return out


def table() -> str:
    lines = [
        "| Query model | Corpus model | Top-1 hit rate, no guard | With model guard |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {q} | {c} | {u} | {g} |" for q, c, u, g in rows()]
    return "\n".join(lines)


if __name__ == "__main__":
    print(table())
