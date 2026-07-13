import pytest

from wordsworth.eval.harness import evaluate

QUERIES = {"q1": "eerste vraag", "q2": "tweede vraag"}
QRELS = {"q1": {"d1": 1, "d2": 1}, "q2": {"d3": 1}}


def _good(query: str) -> list[str]:
    return {"eerste vraag": ["d1", "d2", "d9"], "tweede vraag": ["d3", "d8"]}[query]


def _bad(query: str) -> list[str]:
    # d1 demoted to rank 2; q2's relevant doc missed entirely.
    return {"eerste vraag": ["d9", "d1"], "tweede vraag": ["d8", "d7"]}[query]


def test_report_shape_and_perfect_ranker():
    report = evaluate(_good, QUERIES, QRELS)
    assert set(report) == {"per_query", "aggregate"}
    assert set(report["per_query"]) == {"q1", "q2"}
    for row in report["per_query"].values():
        assert set(row) == {"r_precision", "recall@10", "map", "ndcg@10"}
    for value in report["aggregate"].values():
        assert value == pytest.approx(1.0)


def test_aggregate_is_the_mean_over_queries():
    report = evaluate(_bad, QUERIES, QRELS)
    per_query = report["per_query"]
    # q1: rel {d1,d2}, ranked [d9,d1]. r_prec top2 = 1/2; recall = 1/2; AP = 0.5/2.
    assert per_query["q1"]["r_precision"] == pytest.approx(0.5)
    assert per_query["q1"]["recall@10"] == pytest.approx(0.5)
    assert per_query["q1"]["map"] == pytest.approx(0.25)
    # q2 missed its only relevant doc -> all zero.
    assert per_query["q2"]["map"] == 0.0
    expected_map = (per_query["q1"]["map"] + per_query["q2"]["map"]) / 2
    assert report["aggregate"]["map"] == pytest.approx(expected_map)


def test_same_harness_scores_a_worse_ranker_lower():
    good = evaluate(_good, QUERIES, QRELS)["aggregate"]
    bad = evaluate(_bad, QUERIES, QRELS)["aggregate"]
    for metric in good:
        assert bad[metric] < good[metric]


def test_query_text_missing_for_qrels_id_is_a_hard_error():
    with pytest.raises(KeyError):
        evaluate(_good, {"q1": "eerste vraag"}, QRELS)


def test_k_parameter_is_honoured():
    # relevant doc sits at rank 3; k=2 excludes it, k=10 includes it.
    queries = {"q": "x"}
    qrels = {"q": {"hit": 1}}
    report_k2 = evaluate(lambda _: ["a", "b", "hit"], queries, qrels, k=2)
    report_k10 = evaluate(lambda _: ["a", "b", "hit"], queries, qrels, k=10)
    assert report_k2["per_query"]["q"]["recall@10"] == 0.0
    assert report_k10["per_query"]["q"]["recall@10"] == 1.0
