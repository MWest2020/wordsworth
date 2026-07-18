"""Evaluation run: adapters return ranked external ids, run_evaluation reports
per-config aggregates, and the CLI prints the report from fixture files. Uses
the in-memory index + deterministic embedder — no OpenSearch, Ollama, or DB."""
import pytest

from wordsworth.eval.adapters import bm25_adapter, hybrid_adapter
from wordsworth.eval.run import build_configs, main, run_evaluation

# object_key (external id, the qrels namespace) deliberately differs from the
# internal document id, proving the adapters return the external id.
DOCS = {
    "uuid-1": ("ext_park", "de gemeente Haarlem verleent parkeervergunningen aan bewoners"),
    "uuid-2": ("ext_park2", "aanvraag parkeervergunningen door bewoners van Haarlem centrum"),
    "uuid-3": ("ext_hond", "notulen over hondenbeleid en groenvoorziening in het park"),
    "uuid-4": ("ext_bouw", "de raad besluit over een nieuwe bouwvergunning in het centrum"),
}
QUERIES = {"q1": "parkeervergunningen Haarlem bewoners", "q2": "bouwvergunning centrum raad"}
QRELS = {"q1": {"ext_park": 1, "ext_park2": 1}, "q2": {"ext_bouw": 1}}

QRELS_TREC = "\n".join(
    f"{qid} 0 {doc} {rel}" for qid, rels in QRELS.items() for doc, rel in rels.items()
)
QUERIES_TSV = "\n".join(f"{qid}\t{text}" for qid, text in QUERIES.items())

METRICS = ("r_precision", "recall@10", "map", "ndcg@10")


@pytest.fixture
def loaded_index(mem_index, fake_embedder):
    for doc_id, (key, text) in DOCS.items():
        mem_index.index(doc_id, text, key, vector=fake_embedder.embed([text])[0])
    return mem_index


def test_bm25_adapter_returns_ranked_external_ids(loaded_index):
    ranked = bm25_adapter(loaded_index, k=10)("parkeervergunningen Haarlem bewoners")
    assert ranked[0] in {"ext_park", "ext_park2"}
    assert set(ranked) <= {key for key, _ in DOCS.values()}  # external ids only


def test_hybrid_adapter_returns_ranked_external_ids(loaded_index, fake_embedder):
    ranked = hybrid_adapter(loaded_index, fake_embedder, k=10)("bouwvergunning centrum raad")
    assert "ext_bouw" in ranked
    assert set(ranked) <= {key for key, _ in DOCS.values()}


def test_adapter_respects_k(loaded_index):
    assert len(bm25_adapter(loaded_index, k=1)("Haarlem bewoners centrum park")) == 1


def test_missing_object_key_is_a_hard_error(mem_index):
    mem_index.index("uuid-x", "tekst over parkeervergunningen", None)
    with pytest.raises(ValueError, match="object_key"):
        bm25_adapter(mem_index, k=10)("parkeervergunningen")


def test_run_evaluation_reports_four_metrics_per_config(loaded_index, fake_embedder):
    configs = build_configs(["bm25", "hybrid"], loaded_index, fake_embedder, k=10)
    report = run_evaluation(configs, QUERIES, QRELS, k=10)
    assert set(report) == {"bm25", "hybrid"}
    for aggregates in report.values():
        assert set(aggregates) == set(METRICS)
    # qrels ids = object_keys, so every relevant document is found.
    assert report["bm25"]["recall@10"] == pytest.approx(1.0)
    assert report["hybrid"]["recall@10"] == pytest.approx(1.0)


def test_unknown_config_is_a_hard_error(loaded_index, fake_embedder):
    with pytest.raises(ValueError, match="unknown configuration"):
        build_configs(["bm25", "magic"], loaded_index, fake_embedder)


def test_hybrid_without_embedder_is_a_hard_error(loaded_index):
    with pytest.raises(ValueError, match="embedder"):
        build_configs(["hybrid"], loaded_index, None)


def test_cli_prints_per_config_metrics(loaded_index, fake_embedder, tmp_path, capsys):
    qrels_file = tmp_path / "qrels.txt"
    queries_file = tmp_path / "queries.tsv"
    qrels_file.write_text(QRELS_TREC, encoding="utf-8")
    queries_file.write_text(QUERIES_TSV, encoding="utf-8")

    main(
        ["--qrels", str(qrels_file), "--queries", str(queries_file),
         "--config", "bm25,hybrid"],
        index=loaded_index,
        embedder=fake_embedder,
    )

    out = capsys.readouterr().out
    for config in ("bm25:", "hybrid:"):
        assert config in out
    for metric in METRICS:
        assert metric in out
