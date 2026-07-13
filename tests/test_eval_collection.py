import pytest

from wordsworth.eval.collection import load_qrels, load_queries

QRELS_TREC = """\
q1 0 doc-a 1
q1 0 doc-b 2
q2 0 doc-c 0
q2 0 doc-a 3
"""

QUERIES_TSV = "q1\tparkeervergunning Haarlem\nq2\tbouwvergunning centrum\n"


def test_load_qrels_preserves_graded_relevance(tmp_path):
    path = tmp_path / "qrels.txt"
    path.write_text(QRELS_TREC, encoding="utf-8")
    qrels = load_qrels(path)
    assert qrels == {
        "q1": {"doc-a": 1, "doc-b": 2},
        "q2": {"doc-c": 0, "doc-a": 3},
    }


def test_load_queries_round_trip(tmp_path):
    path = tmp_path / "queries.tsv"
    path.write_text(QUERIES_TSV, encoding="utf-8")
    queries = load_queries(path)
    assert queries == {
        "q1": "parkeervergunning Haarlem",
        "q2": "bouwvergunning centrum",
    }


def test_loaders_feed_the_runner(tmp_path):
    from wordsworth.eval.harness import evaluate

    (tmp_path / "qrels.txt").write_text(QRELS_TREC, encoding="utf-8")
    (tmp_path / "queries.tsv").write_text(QUERIES_TSV, encoding="utf-8")
    qrels = load_qrels(tmp_path / "qrels.txt")
    queries = load_queries(tmp_path / "queries.tsv")
    report = evaluate(lambda q: ["doc-a"], queries, qrels)
    assert set(report["per_query"]) == {"q1", "q2"}


def test_blank_lines_are_ignored(tmp_path):
    path = tmp_path / "qrels.txt"
    path.write_text("\nq1 0 doc-a 1\n\n", encoding="utf-8")
    assert load_qrels(path) == {"q1": {"doc-a": 1}}


def test_malformed_qrels_line_is_a_hard_error(tmp_path):
    path = tmp_path / "qrels.txt"
    path.write_text("q1 0 doc-a\n", encoding="utf-8")  # only 3 columns
    with pytest.raises(ValueError):
        load_qrels(path)


def test_malformed_queries_line_is_a_hard_error(tmp_path):
    path = tmp_path / "queries.tsv"
    path.write_text("q1 no-tab-here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_queries(path)
