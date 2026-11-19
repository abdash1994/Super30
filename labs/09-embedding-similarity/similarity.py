"""Cosine similarity over embeddings, with guards against mixing models.

Every vector carries the name of the model that produced it. Comparing two
vectors from different models raises instead of returning a number, because
that number would look valid and mean nothing.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class EmbeddingMismatchError(ValueError):
    """Two embeddings cannot be compared (different model or dimension)."""


@dataclass(frozen=True)
class Embedding:
    model: str
    vector: np.ndarray

    @property
    def dim(self) -> int:
        return int(self.vector.shape[0])


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Raw cosine similarity between two 1-D vectors. No model check.

    Returns a value in [-1, 1]. Raises on zero vectors or shape mismatch.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise EmbeddingMismatchError(f"dimension mismatch: {a.shape[0]} vs {b.shape[0]}")
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        raise ValueError("cosine is undefined for a zero vector")
    return float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))


def check_compatible(a: Embedding, b: Embedding) -> None:
    if a.model != b.model:
        raise EmbeddingMismatchError(
            f"model mismatch: '{a.model}' vs '{b.model}'. "
            "Re-embed one side with the same model before comparing."
        )
    if a.dim != b.dim:
        raise EmbeddingMismatchError(f"dimension mismatch: {a.dim} vs {b.dim}")


def safe_cosine(a: Embedding, b: Embedding) -> float:
    """Cosine similarity that refuses to compare embeddings from different models."""
    check_compatible(a, b)
    return cosine(a.vector, b.vector)


def top_k(
    query: Embedding,
    corpus: dict[str, Embedding],
    k: int = 3,
    *,
    check: bool = True,
) -> list[tuple[str, float]]:
    """Rank corpus items by cosine similarity to the query, highest first.

    With check=False the model guard is skipped, which is how the mixed-model
    failure is demonstrated (the dimensions still have to match).
    """
    scored = []
    for doc_id, emb in corpus.items():
        score = safe_cosine(query, emb) if check else cosine(query.vector, emb.vector)
        scored.append((doc_id, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:k]


def hit_rate(
    queries: list[tuple[Embedding, str]],
    corpus: dict[str, Embedding],
    *,
    check: bool = True,
) -> float:
    """Share of queries whose top-1 result is the expected document."""
    hits = sum(1 for q, expected in queries if top_k(q, corpus, k=1, check=check)[0][0] == expected)
    return hits / len(queries)
