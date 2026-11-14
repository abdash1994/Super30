"""Small, hand-made fixture embeddings so the lab and CI need no model or network.

"model-a" uses 8 readable axes. "model-b" has the SAME 8 dimensions but is a
fixed random rotation of model-a's space: inside model-b every similarity is
identical to model-a (a rotation preserves angles), yet a model-a vector and a
model-b vector point in unrelated directions. That is what two real embedding
models look like to each other. "model-c" is a smaller 4-dimensional model.
"""
from __future__ import annotations

import numpy as np

from similarity import Embedding

AXES = ["billing", "refund", "login", "password", "shipping", "delay", "api", "error"]

DOCS_A = {
    "refund-policy":      [0.6, 0.9, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0],
    "double-charge":      [0.9, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2],
    "reset-password":     [0.0, 0.0, 0.5, 0.9, 0.0, 0.0, 0.0, 0.0],
    "sso-login-loop":     [0.0, 0.0, 0.9, 0.2, 0.0, 0.0, 0.1, 0.4],
    "late-delivery":      [0.0, 0.1, 0.0, 0.0, 0.7, 0.8, 0.0, 0.0],
    "tracking-number":    [0.0, 0.0, 0.0, 0.0, 0.9, 0.2, 0.1, 0.0],
    "api-rate-limit":     [0.0, 0.0, 0.0, 0.0, 0.0, 0.3, 0.9, 0.5],
    "webhook-500":        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6, 0.9],
}

# (query vector in model-a space, the doc a human would pick)
QUERIES_A = [
    ([0.5, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "refund-policy"),        # "can I get my money back"
    ([1.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3], "double-charge"),        # "charged twice"
    ([0.0, 0.0, 0.4, 1.0, 0.0, 0.0, 0.0, 0.1], "reset-password"),       # "forgot my password"
    ([0.0, 0.0, 1.0, 0.1, 0.0, 0.0, 0.0, 0.5], "sso-login-loop"),       # "login keeps redirecting"
    ([0.0, 0.0, 0.0, 0.0, 0.6, 1.0, 0.0, 0.0], "late-delivery"),        # "parcel is late"
    ([0.0, 0.0, 0.0, 0.0, 1.0, 0.1, 0.0, 0.0], "tracking-number"),      # "where is my order"
    ([0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 1.0, 0.3], "api-rate-limit"),       # "429 too many requests"
    ([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 1.0], "webhook-500"),          # "webhook failing"
]

_ROTATION = np.linalg.qr(np.random.default_rng(seed=9).normal(size=(8, 8)))[0]
_PROJECTION = np.random.default_rng(seed=19).normal(size=(4, 8))


def _a(vec) -> np.ndarray:
    return np.asarray(vec, dtype=float)


def embed(vec, model: str) -> Embedding:
    """Turn a model-a fixture vector into that model's embedding."""
    v = _a(vec)
    if model == "model-a":
        return Embedding("model-a", v)
    if model == "model-b":
        return Embedding("model-b", _ROTATION @ v)
    if model == "model-c":
        return Embedding("model-c", _PROJECTION @ v)
    raise ValueError(f"unknown fixture model: {model}")


def corpus(model: str) -> dict[str, Embedding]:
    return {doc_id: embed(vec, model) for doc_id, vec in DOCS_A.items()}


def queries(model: str) -> list[tuple[Embedding, str]]:
    return [(embed(vec, model), expected) for vec, expected in QUERIES_A]
