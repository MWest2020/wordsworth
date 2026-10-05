# SPDX-License-Identifier: MIT
"""The final order of hybrid search, behind a setting (long-documents-rank-fairly).

"cosine" re-sorts the recall set by whole-document cosine; "rrf" keeps the
fused rank the recall stage computed. The default is rrf since 2026-10-05, the
measurement's pick; cosine stays as the rollback.
"""
import pytest

from wordsworth.hybrid import hybrid_search
from wordsworth.search_index import Hit


class _Recall:
    """An index whose recall set comes back in a fixed fused order, where the
    fused leader has the WORST cosine -- the long document of the measurement."""

    def hybrid_search(self, query, query_vector, recall=50, only=None, topic=None, **kw):
        return [Hit("long", 0.0, "k-long", [0.2, 1.0]),
                Hit("mid", 0.0, "k-mid", [0.7, 0.7]),
                Hit("short", 0.0, "k-short", [1.0, 0.0])]


class _Embed:
    dim = 2

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def _order(**kw):
    return [h.document_id for h in hybrid_search(_Recall(), _Embed(), "q", size=3, **kw)]


def test_cosine_resorts_the_recall_set():
    assert _order(final="cosine") == ["short", "mid", "long"]


def test_rrf_keeps_the_fused_rank_and_still_reports_cosine():
    hits = hybrid_search(_Recall(), _Embed(), "q", size=3, final="rrf")
    assert [h.document_id for h in hits] == ["long", "mid", "short"]
    assert hits[2].score == 1.0          # the score is still the cosine


def test_the_default_is_rrf_and_cosine_is_the_rollback(monkeypatch):
    """Since 2026-10-05 (long-documents-rank-fairly): the spec says the final
    ranking keeps the fused rank, so that is what an unset environment gets."""
    monkeypatch.delenv("WORDSWORTH_HYBRID_FINAL_RANK", raising=False)
    assert _order() == ["long", "mid", "short"]
    monkeypatch.setenv("WORDSWORTH_HYBRID_FINAL_RANK", "cosine")
    assert _order() == ["short", "mid", "long"]


def test_an_unknown_mode_is_an_error_not_a_fallback(monkeypatch):
    with pytest.raises(ValueError):
        _order(final="bm25")
    monkeypatch.setenv("WORDSWORTH_HYBRID_FINAL_RANK", "cosinus")
    with pytest.raises(ValueError):
        _order()
