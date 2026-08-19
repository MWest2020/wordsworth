"""Driver-side chunking of the anonymize call (point 3b / GLiNER OOM fix)."""
from __future__ import annotations

import wordsworth.openanonymiser_driver as drv
from wordsworth.openanonymiser_driver import _chunk_text, _openanonymiser_redact


def test_chunks_concatenate_back_exactly():
    text = "".join(f"regel {i} met wat tekst\n" for i in range(500))
    chunks = _chunk_text(text, 200)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    assert "".join(chunks) == text          # lossless: pieces rebuild the original


def test_chunk_hard_splits_a_single_overlong_line():
    text = "x" * 1000                        # no newlines
    chunks = _chunk_text(text, 300)
    assert all(len(c) <= 300 for c in chunks)
    assert "".join(chunks) == text


def test_short_text_is_one_chunk():
    assert _chunk_text("kort", 4000) == ["kort"]


def test_redact_chunks_reassembles_and_sums_counts(monkeypatch):
    # Force chunking small, and stub the per-chunk HTTP call.
    monkeypatch.setattr(type(drv.settings), "anonymize_chunk_chars",
                        property(lambda self: 10))

    def fake_redact_one(chunk: str):
        # Pretend each chunk yields its (upper-cased) text + one 'person' hit.
        return chunk.upper(), {"person": 1}

    monkeypatch.setattr(drv, "_redact_one", fake_redact_one)
    text = "jan jansen woont in amsterdam bij de gracht"   # > 10 chars → chunked
    redacted, counts = _openanonymiser_redact(text)
    assert redacted == text.upper()          # chunks reassembled in order
    assert counts["person"] >= 2             # summed across chunks
