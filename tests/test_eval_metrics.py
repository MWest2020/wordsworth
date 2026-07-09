from math import log2

import pytest

from wordsworth.eval.metrics import (
    average_precision,
    ndcg_at_k,
    r_precision,
    recall_at_k,
)


def test_r_precision_all_relevant_in_top_r():
    # 2 relevant docs, both in the top 2 -> 1.0
    qrels = {"a": 1, "b": 1}
    assert r_precision(["a", "b", "c"], qrels) == 1.0


def test_r_precision_partial():
    # R = 2, only 1 of the top 2 is relevant -> 0.5
    qrels = {"a": 1, "b": 1}
    assert r_precision(["a", "x", "b"], qrels) == 0.5


def test_recall_at_10_counts_relevant_in_top_k():
    # 3 of 5 relevant appear in the top 10 -> 0.6
    qrels = {"r1": 1, "r2": 1, "r3": 1, "r4": 1, "r5": 1}
    ranked = ["r1", "x", "r2", "y", "r3", "z"]
    assert recall_at_k(ranked, qrels, k=10) == pytest.approx(0.6)


def test_average_precision_hand_computed():
    # rel = {a, c}, R = 2. hits at rank 1 (p=1) and rank 3 (p=2/3).
    qrels = {"a": 1, "c": 1}
    expected = (1.0 + (2 / 3)) / 2
    assert average_precision(["a", "b", "c", "d"], qrels) == pytest.approx(expected)


def test_average_precision_rewards_early_hits():
    qrels = {"a": 1, "b": 1}
    early = average_precision(["a", "b", "x", "y"], qrels)
    late = average_precision(["x", "y", "a", "b"], qrels)
    assert early > late


def test_ndcg_ideal_order_is_one():
    qrels = {"a": 3, "b": 2, "c": 1}
    assert ndcg_at_k(["a", "b", "c"], qrels, k=10) == pytest.approx(1.0)


def test_ndcg_non_ideal_below_one_and_hand_computed():
    qrels = {"a": 3, "b": 2, "c": 1}
    dcg = 1 / log2(2) + 2 / log2(3) + 3 / log2(4)  # ranked c, b, a
    idcg = 3 / log2(2) + 2 / log2(3) + 1 / log2(4)
    assert ndcg_at_k(["c", "b", "a"], qrels, k=10) == pytest.approx(dcg / idcg)


def test_ndcg_earlier_high_grade_scores_higher():
    qrels = {"a": 3, "b": 1}
    better = ndcg_at_k(["a", "b"], qrels, k=10)
    worse = ndcg_at_k(["b", "a"], qrels, k=10)
    assert better > worse


def test_no_relevant_documents_yields_zero():
    qrels = {"a": 0, "b": 0}  # graded 0 = not relevant
    ranked = ["a", "b", "c"]
    assert r_precision(ranked, qrels) == 0.0
    assert recall_at_k(ranked, qrels) == 0.0
    assert average_precision(ranked, qrels) == 0.0
    assert ndcg_at_k(ranked, qrels) == 0.0


def test_empty_qrels_yields_zero():
    assert r_precision(["a"], {}) == 0.0
    assert recall_at_k(["a"], {}) == 0.0
    assert average_precision(["a"], {}) == 0.0
    assert ndcg_at_k(["a"], {}) == 0.0
