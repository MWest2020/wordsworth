# SPDX-License-Identifier: MIT
"""Why a result matched: the passage of a hit closest to the question.

Explain, don't re-rank (change search-matching-passage). The order of the hits
is decided elsewhere and nothing here touches it: this module only picks, for
each of the first ten hits on a page, the passage whose stored vector is closest
to the question's, and says what that passage shares with the question.

Three things hold here on purpose:

- The shown text is ``text[s:e]`` of the STORED pseudonymised text, so it stays
  a quotation of what the index holds -- never a re-joined copy of it.
- Marking is data, not markup: the answer is a list of segments (a piece of the
  text, marked or not). The template writes each one through autoescape; no
  HTML is built here, so a ``<script>`` in a document arrives as text.
- When the passage cannot be determined the hit keeps today's fragment, and
  when the cause is the index (or the second embedding of the question), the
  page says so. A missing explanation must not look like an explanation.
"""
from __future__ import annotations

import logging
import re

from zeef.similarity import cosine

from .console_data import _WORD
from .passage_reads import MAX_IDS
from .passages import split_spans
from .search_index import SearchUnavailable

log = logging.getLogger("wordsworth.search")

#: A query word counts from this many characters on, so "de" and "van" are
#: neither marked nor turn every reason into "both". A rule of thumb.
MIN_WORD = 4
#: The shown window: this many characters before the first marked word, and
#: this many in all. A passage of 200 words is too long for a result row.
BEFORE = 80
WIDTH = 320

WORDS_AND_MEANING = "op woorden en betekenis"
MEANING = "op betekenis"
WORDS = "op woorden"


def _pattern(query: str) -> re.Pattern | None:
    """The query words of ``MIN_WORD`` characters or more, case-insensitive and
    at a word start (as `console_data.fragment`): "vergunning" also finds
    "vergunningen", never the "gunning" inside it. The whole word is marked."""
    words = sorted({w.lower() for w in _WORD.findall(query or "")
                    if len(w) >= MIN_WORD}, key=len, reverse=True)
    if not words:
        return None
    return re.compile(r"\b(?:" + "|".join(map(re.escape, words)) + r")\w*",
                      re.IGNORECASE)


def _window(text: str, s: int, e: int, at: int) -> tuple[int, int]:
    """A window inside [s, e) around ``at``, cut at whitespace, never mid-word."""
    start = max(s, at - BEFORE)
    end = min(e, start + WIDTH)
    if start > s and not text[start - 1].isspace():
        gap = re.compile(r"\s+").search(text, start, at)
        start = gap.end() if gap else at
    if end < e and not text[end].isspace():
        cut = max((m.start() for m in re.finditer(r"\s", text[at:end])),
                  default=0)
        end = at + cut if cut else end
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def segments(text: str, start: int, end: int,
             pattern: re.Pattern | None) -> list[dict]:
    """``text[start:end]`` as pieces, each marked or not; joined, they are
    exactly ``text[start:end]``."""
    out, at = [], start
    for m in (pattern.finditer(text, start, end) if pattern else ()):
        if m.start() > at:
            out.append({"text": text[at:m.start()], "marked": False})
        out.append({"text": m.group(0), "marked": True})
        at = m.end()
    if at < end:
        out.append({"text": text[at:end], "marked": False})
    return out


def best(text: str, vectors: list[list[float]], query_vector: list[float],
         query: str) -> dict | None:
    """The passage of ``text`` closest to the question, or None.

    None when the number of stored vectors differs from the number of windows
    the text splits into (indexed under another passage size, or the text
    changed without a reindex), and when there are no vectors at all: a vector
    that belongs to another window would point at the wrong words.
    """
    spans = split_spans(text or "")
    if not spans or len(vectors) != len(spans):
        return None
    scores = [cosine(query_vector, v) for v in vectors]
    i = max(range(len(scores)), key=scores.__getitem__)
    s, e = spans[i]
    pattern = _pattern(query)
    first = pattern.search(text, s, e) if pattern else None
    start, end = _window(text, s, e, first.start() if first else s)
    words = sorted({m.group(0).lower() for m in pattern.finditer(text, s, e)}
                   ) if pattern else []
    return {
        "span": (s, e), "shown": (start, end),
        "segments": segments(text, start, end, pattern),
        "words": words, "reason": WORDS_AND_MEANING if words else MEANING,
        "cut_before": start > 0, "cut_after": end < len(text),
    }


def annotate(index, embedder, query: str, hits: list[dict],
             texts: list[str]) -> bool:
    """Give the first ``MAX_IDS`` hits their closest passage and reason.

    ``hits`` are the console's result rows, in order; ``texts`` their stored
    texts. Sets ``passage`` and ``reden`` on the rows it can explain and leaves
    the rest on today's fragment. Returns True when the passages are
    unavailable -- the index could not be read, or the question could not be
    embedded a second time -- so the page can say so. The rows stay: the search
    itself succeeded, and a page without results would hide that.
    """
    shown = list(zip(hits, texts))[:MAX_IDS]
    if embedder is None:              # keyword search: no question vector
        for hit, _text in shown:
            hit["reden"] = WORDS
        return False
    if not shown:
        return False
    try:
        # hybrid_search embeds the question and keeps the vector to itself;
        # changing what it returns would touch the module that orders the hits.
        query_vector = embedder.embed([query])[0]
    except Exception as exc:
        log.warning("passages unavailable: question embedding failed (%s)",
                    type(exc).__name__)
        return True
    try:
        vectors = index.passages_of([hit["id"] for hit, _text in shown])
    except SearchUnavailable as exc:
        log.warning("passages unavailable: %s", exc)
        return True
    for hit, text in shown:
        passage = best(text, vectors.get(hit["id"]) or [], query_vector, query)
        if passage is not None:
            hit["passage"], hit["reden"] = passage, passage["reason"]
    return False
