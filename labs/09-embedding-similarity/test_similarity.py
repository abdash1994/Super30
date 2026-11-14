import math

import numpy as np
import pytest

import fixtures
from demo import table
from similarity import (
    Embedding,
    EmbeddingMismatchError,
    cosine,
    hit_rate,
    safe_cosine,
    top_k,
)


# --- cosine basics -----------------------------------------------------------

def test_identical_vectors_score_one():
    assert cosine([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_orthogonal_vectors_score_zero():
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)


def test_opposite_vectors_score_minus_one():
    assert cosine([1, 2], [-1, -2]) == pytest.approx(-1.0)


def test_cosine_ignores_length_only_direction_counts():
    assert cosine([1, 1], [10, 10]) == pytest.approx(1.0)


def test_zero_vector_is_rejected():
    with pytest.raises(ValueError):
        cosine([0, 0, 0], [1, 2, 3])


def test_matches_hand_calculation():
    # (1*4 + 2*5 + 3*6) / (sqrt(14) * sqrt(77))
    expected = 32 / (math.sqrt(14) * math.sqrt(77))
    assert cosine([1, 2, 3], [4, 5, 6]) == pytest.approx(expected)


# --- same model: search works -----------------------------------------------

@pytest.mark.parametrize("model", ["model-a", "model-b", "model-c"])
def test_same_model_search_finds_the_right_doc_every_time(model):
    assert hit_rate(fixtures.queries(model), fixtures.corpus(model)) == 1.0


def test_top_k_is_sorted_highest_first():
    q, _ = fixtures.queries("model-a")[0]
    scores = [s for _, s in top_k(q, fixtures.corpus("model-a"), k=8)]
    assert scores == sorted(scores, reverse=True)


def test_rotated_model_keeps_the_same_internal_similarities():
    a = fixtures.corpus("model-a")
    b = fixtures.corpus("model-b")
    pair = ("refund-policy", "double-charge")
    assert safe_cosine(b[pair[0]], b[pair[1]]) == pytest.approx(safe_cosine(a[pair[0]], a[pair[1]]))


# --- mixed models: what breaks ----------------------------------------------

def test_mixed_models_with_same_dimensions_fail_silently():
    """No error, plausible-looking scores, wrong answers."""
    qs, docs = fixtures.queries("model-a"), fixtures.corpus("model-b")
    for q, _ in qs:
        results = top_k(q, docs, k=1, check=False)  # runs without complaint
        assert -1.0 <= results[0][1] <= 1.0
    assert hit_rate(qs, docs, check=False) <= 0.25


def test_guard_refuses_mixed_models():
    q, _ = fixtures.queries("model-a")[0]
    with pytest.raises(EmbeddingMismatchError, match="model mismatch"):
        top_k(q, fixtures.corpus("model-b"))


def test_different_dimensions_fail_loudly_even_without_the_guard():
    q, _ = fixtures.queries("model-a")[0]
    with pytest.raises(EmbeddingMismatchError, match="dimension mismatch"):
        top_k(q, fixtures.corpus("model-c"), check=False)


def test_guard_also_catches_same_name_wrong_dimension():
    a = Embedding("model-x", np.ones(4))
    b = Embedding("model-x", np.ones(8))
    with pytest.raises(EmbeddingMismatchError, match="dimension mismatch"):
        safe_cosine(a, b)


def test_demo_table_shows_the_drop():
    out = table()
    assert "| model-a | model-a | 100% | 100% |" in out
    assert "| model-a | model-b | 0% | refused |" in out
    assert "error: dims differ" in out
