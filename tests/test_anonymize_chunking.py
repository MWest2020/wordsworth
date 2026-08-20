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


def test_concurrent_chunks_preserve_order(monkeypatch):
    # Chunks may complete out of order; the result must still be in chunk order.
    import time

    monkeypatch.setattr(type(drv.settings), "anonymize_chunk_chars",
                        property(lambda self: 5))
    monkeypatch.setattr(type(drv.settings), "anonymize_concurrency",
                        property(lambda self: 4))

    def slow_first(chunk: str):
        # Earlier chunks sleep longer, so they finish last — a naive
        # append-on-completion would scramble the order.
        time.sleep(0.05 if chunk.startswith("a") else 0.0)
        return chunk, {}

    monkeypatch.setattr(drv, "_redact_one", slow_first)
    text = "aaaaabbbbbcccccddddd"                # 4 chunks of 5
    redacted, _ = _openanonymiser_redact(text)
    assert redacted == text                      # order preserved despite timing


def test_one_failing_chunk_propagates(monkeypatch):
    # Fail-hard: a single failing chunk must raise, never return partial text.
    monkeypatch.setattr(type(drv.settings), "anonymize_chunk_chars",
                        property(lambda self: 5))

    def sometimes_fails(chunk: str):
        if chunk.startswith("b"):
            raise RuntimeError("engine boom")
        return chunk, {}

    monkeypatch.setattr(drv, "_redact_one", sometimes_fails)
    try:
        _openanonymiser_redact("aaaaabbbbbccccc")
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("a failing chunk must propagate, not be swallowed")
