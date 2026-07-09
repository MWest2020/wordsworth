"""Loaders for a standard on-disk test collection, so a real collection (e.g. the
thesis's 47 queries + judgments) drops in without code changes.

- qrels: TREC format — whitespace-separated `query_id  0  doc_id  relevance` per
  line; the second column (iteration) is ignored.
- queries: TSV — `query_id<TAB>query text` per line.

Loaders return the in-memory dicts the runner consumes; the metric/harness core
never touches files. Malformed lines are a hard error (no silent fallbacks)."""
from __future__ import annotations

from pathlib import Path


def load_qrels(path: str | Path) -> dict[str, dict[str, int]]:
    """Parse TREC-format qrels into {query_id: {doc_id: relevance}}."""
    qrels: dict[str, dict[str, int]] = {}
    for lineno, raw in enumerate(_lines(path), start=1):
        parts = raw.split()
        if len(parts) != 4:
            raise ValueError(f"qrels line {lineno}: want 4 columns, got {raw!r}")
        qid, _iteration, doc_id, relevance = parts
        qrels.setdefault(qid, {})[doc_id] = int(relevance)
    return qrels


def load_queries(path: str | Path) -> dict[str, str]:
    """Parse TSV queries into {query_id: query text}."""
    queries: dict[str, str] = {}
    for lineno, raw in enumerate(_lines(path), start=1):
        qid, tab, text = raw.partition("\t")
        if not tab:
            raise ValueError(f"queries line {lineno}: want a TAB, got {raw!r}")
        queries[qid.strip()] = text.strip()
    return queries


def _lines(path: str | Path) -> list[str]:
    """Non-blank lines, trailing newline stripped."""
    content = Path(path).read_text(encoding="utf-8")
    return [line for line in content.splitlines() if line.strip()]
