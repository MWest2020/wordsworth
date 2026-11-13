# SPDX-License-Identifier: MIT
"""Passages: a vector per passage, so a long document is not one averaged vector.

One embedding per whole document stands for everything in it, so a long
document sits further from any one question than a short one vaguely about the
same thing. Measured on the Woo collection (change long-documents-rank-fairly):
not one of 35 long documents was found by its own title. Scoring a document by
its best passage removes that by construction.

The split is a fixed rule, not tuned: windows of ``WORDS`` words starting every
``STRIDE`` words, so neighbours overlap by ``WORDS - STRIDE``. 200 words is
about a paragraph -- short enough that one subject dominates, well inside
bge-m3's context. This is the setting that was measured (candidate 2a).
"""
from __future__ import annotations

import re

from .config import settings
from .embedder import Embedder
from .retry import retry_transient

WORDS = 200
STRIDE = 150


def _windows(n: int, words: int, stride: int) -> list[tuple[int, int]]:
    """The windows as token ranges [start, end) over ``n`` tokens -- the one
    rule both `split` and `split_spans` follow, so they cannot drift apart."""
    if not n:
        return []
    starts = range(0, max(n - words, 0) + 1, stride)
    out = [(s, min(s + words, n)) for s in starts]
    if starts[-1] + words < n:    # the tail the stride stepped over
        out.append((n - words, n))
    return out


def split(text: str, words: int = WORDS, stride: int = STRIDE) -> list[str]:
    """Overlapping word windows covering the whole text; a text no longer than
    one window is one passage, and an empty text none."""
    tokens = text.split()
    return [" ".join(tokens[s:e]) for s, e in _windows(len(tokens), words, stride)]


def split_spans(text: str, words: int = WORDS,
                stride: int = STRIDE) -> list[tuple[int, int]]:
    """The windows of `split` as character offsets into ``text``.

    `split` joins a window's words with single spaces, so a passage is not a
    substring of the text; ``text[s:e]`` is, and ``" ".join(text[s:e].split())``
    is the passage `split` gives at the same position (change
    search-matching-passage: the console quotes the stored text, never a
    re-joined copy of it). ``\\S+`` and `str.split` cut at the same whitespace.
    """
    tokens = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    return [(tokens[s][0], tokens[e - 1][1])
            for s, e in _windows(len(tokens), words, stride)]


def embed_passages(embedder: Embedder, text: str) -> list[list[float]]:
    """One vector per passage of ``text``, each with the bounded retry ingest
    uses. A failed passage is a failed document: no partial set of passages,
    which would rank a document by the passages that happened to embed."""
    return [retry_transient(lambda p=p: embedder.embed([p])[0],
                            settings.retry_attempts, settings.retry_base_delay,
                            what="passage_embed")
            for p in split(text)]
