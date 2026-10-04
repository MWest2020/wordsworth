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

from .config import settings
from .embedder import Embedder
from .retry import retry_transient

WORDS = 200
STRIDE = 150


def split(text: str, words: int = WORDS, stride: int = STRIDE) -> list[str]:
    """Overlapping word windows covering the whole text; a text no longer than
    one window is one passage, and an empty text none."""
    tokens = text.split()
    if not tokens:
        return []
    starts = range(0, max(len(tokens) - words, 0) + 1, stride)
    out = [" ".join(tokens[s:s + words]) for s in starts]
    last = starts[-1] + words
    if last < len(tokens):        # the tail the stride stepped over
        out.append(" ".join(tokens[-words:]))
    return out


def embed_passages(embedder: Embedder, text: str) -> list[list[float]]:
    """One vector per passage of ``text``, each with the bounded retry ingest
    uses. A failed passage is a failed document: no partial set of passages,
    which would rank a document by the passages that happened to embed."""
    return [retry_transient(lambda p=p: embedder.embed([p])[0],
                            settings.retry_attempts, settings.retry_base_delay,
                            what="passage_embed")
            for p in split(text)]
