"""Evaluation run: per-configuration aggregate metrics over a loaded collection.

`run_evaluation(configs, queries, qrels, k)` calls the harness `evaluate` per
configuration and collects the aggregate metrics into one report. The CLI

    python -m wordsworth.eval.run --qrels QRELS --queries QUERIES \
        --config bm25,hybrid [--k 10]

loads the collection via the harness loaders (TREC qrels + TSV queries), runs
the chosen configurations over the indexed corpus, and prints the report.
Precondition: the corpus is ingested with `object_key` = the qrels' document
ids. A real hybrid run needs OpenSearch + local bge-m3 (Ollama) — no cloud.
An unknown configuration name is a hard error, not a silent skip."""
from __future__ import annotations

import argparse
from collections.abc import Mapping

from ..embedder import Embedder
from ..search_index import SearchIndex
from .adapters import Ranker, bm25_adapter, hybrid_adapter
from .collection import load_qrels, load_queries
from .harness import evaluate

_METRICS = ("r_precision", "recall@10", "map", "ndcg@10")


def run_evaluation(
    configs: Mapping[str, Ranker],
    queries: Mapping[str, str],
    qrels: Mapping[str, Mapping[str, int]],
    k: int = 10,
) -> dict[str, dict[str, float]]:
    """Return {config_name: {metric: aggregate mean}} per configuration."""
    return {
        name: evaluate(search, queries, qrels, k)["aggregate"]
        for name, search in configs.items()
    }


def build_configs(
    names: list[str],
    index: SearchIndex,
    embedder: Embedder | None,
    k: int = 10,
) -> dict[str, Ranker]:
    """Map configuration names to ranker adapters. Unknown name = hard error."""
    configs: dict[str, Ranker] = {}
    for name in names:
        if name == "bm25":
            configs[name] = bm25_adapter(index, k)
        elif name == "hybrid":
            if embedder is None:
                raise ValueError("hybrid configuration needs an embedder")
            configs[name] = hybrid_adapter(index, embedder, k)
        else:
            raise ValueError(f"unknown configuration {name!r} (want: bm25, hybrid)")
    return configs


def format_report(report: Mapping[str, Mapping[str, float]]) -> str:
    lines = []
    for name, aggregates in report.items():
        metrics = "  ".join(f"{m}={aggregates[m]:.4f}" for m in _METRICS)
        lines.append(f"{name}: {metrics}")
    return "\n".join(lines)


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m wordsworth.eval.run",
        description="Run the IR evaluation over the indexed corpus.",
    )
    parser.add_argument("--qrels", required=True, help="TREC-format qrels file")
    parser.add_argument("--queries", required=True, help="TSV queries file")
    parser.add_argument(
        "--config", default="bm25,hybrid",
        help="comma-separated configurations (bm25, hybrid)",
    )
    parser.add_argument("--k", type=int, default=10, help="ranking depth")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    index: SearchIndex | None = None,
    embedder: Embedder | None = None,
) -> None:
    """CLI entry point. `index`/`embedder` are injectable seams for tests;
    the defaults are the real drivers (OpenSearch, local Ollama bge-m3)."""
    args = _parse(argv)
    names = [n.strip() for n in args.config.split(",") if n.strip()]
    if not names:
        raise ValueError("--config names no configuration")
    if index is None:
        from ..opensearch_index import OpenSearchIndex

        index = OpenSearchIndex.from_config()
    if embedder is None and "hybrid" in names:
        from ..embedder import OllamaEmbedder

        embedder = OllamaEmbedder.from_config()
    queries = load_queries(args.queries)
    qrels = load_qrels(args.qrels)
    report = run_evaluation(build_configs(names, index, embedder, args.k),
                            queries, qrels, args.k)
    print(format_report(report))


if __name__ == "__main__":
    main()
