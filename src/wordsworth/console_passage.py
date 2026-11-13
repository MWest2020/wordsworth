# SPDX-License-Identifier: MIT
"""Why a result matched: the passage of a hit closest to the question.

Explain, don't re-rank (change search-matching-passage). The order of the hits
is decided elsewhere and nothing here touches it: this module picks, for each
of the first ten hits on a page, the passage whose stored vector is closest to
the question's, and says what that passage shares with the question.

- The shown text is ``text[s:e]`` of the STORED pseudonymised text: a
  quotation of what the index holds, never a re-joined copy of it.
- Marking is data, not markup: a list of segments (a piece of the text, marked
  or not) that the template writes through autoescape. No HTML is built here.
- A pseudonym token (``[PERSOON:9f8e7d6c]``) is never marked, counted or cut.
- When the passage cannot be determined the hit keeps today's fragment; when
  the cause is the index or the second embedding, the page says so. Whatever
  goes wrong here costs the explanation, never the page of results.
"""
from __future__ import annotations

import logging
import re

from zeef.similarity import cosine

from .config import settings
from .console_data import _TOKEN, _WORD
from .passage_reads import MAX_IDS
from .passages import split_spans
from .retry import retry_transient

log = logging.getLogger("wordsworth.search")

#: A query word counts from this many characters on, so "de" and "van" are
#: neither marked nor turn every reason into "both". A rule of thumb.
MIN_WORD = 4
#: The shown window: this many characters before the first marked word, and
#: this many in all. A passage of 200 words is too long for a result row.
BEFORE = 80
WIDTH = 320
#: A document with more passages than this is not read: at about 20 kB of JSON
#: per vector that is 4 MB for one document. Its hit shows today's fragment.
MAX_PASSAGES = 200

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


def _matches(text: str, s: int, e: int, pattern, tokens) -> list[re.Match]:
    """The query-word matches in [s, e) that do not touch a pseudonym token."""
    if pattern is None:
        return []
    return [m for m in pattern.finditer(text, s, e)
            if not any(a < m.end() and m.start() < b for a, b in tokens)]


def _window(text: str, s: int, e: int, at: int, tokens) -> tuple[int, int]:
    """A window inside [s, e) around ``at``, cut at whitespace, never mid-word
    and never inside a pseudonym token."""
    start = max(s, at - BEFORE)
    end = min(e, start + WIDTH)
    if start > s and not text[start - 1].isspace():
        gap = re.compile(r"\s+").search(text, start, at)
        start = gap.end() if gap else at
    if end < e and not text[end].isspace():
        cut = max((m.start() for m in re.finditer(r"\s", text[at:end])),
                  default=0)
        end = at + cut if cut else end
    for a, b in tokens:              # a token is whole or absent, never halved
        start = a if a < start < b else start
        end = b if a < end < b else end
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def segments(text: str, start: int, end: int, found) -> list[dict]:
    """``text[start:end]`` as pieces, each marked or not; joined, they are
    exactly ``text[start:end]``. ``found`` are the matches to mark."""
    out, at = [], start
    for m in found:
        if m.start() < start or m.end() > end:
            continue
        if m.start() > at:
            out.append({"text": text[at:m.start()], "marked": False})
        out.append({"text": m.group(0), "marked": True})
        at = m.end()
    if at < end:
        out.append({"text": text[at:end], "marked": False})
    return out


def best(text: str, vectors: list[list[float]], query_vector: list[float],
         query: str, spans: list[tuple[int, int]] | None = None) -> dict | None:
    """The passage of ``text`` closest to the question, or None.

    None when the number of stored vectors differs from the number of windows
    the text splits into (indexed under another passage size, or the text
    changed without a reindex), when there are none, and when they have another
    dimension than the question's (another embedder; the caller logs that): a
    vector that belongs to another window or model points at the wrong words.
    """
    spans = split_spans(text or "") if spans is None else spans
    if not spans or len(vectors) != len(spans):
        return None
    if any(len(v) != len(query_vector) for v in vectors):
        return None
    scores = [cosine(query_vector, v) for v in vectors]
    s, e = spans[max(range(len(scores)), key=scores.__getitem__)]
    tokens = [(m.start(), m.end()) for m in _TOKEN.finditer(text, max(0, s - 64),
                                                            e + 64)]
    found = _matches(text, s, e, _pattern(query), tokens)
    start, end = _window(text, s, e, found[0].start() if found else s, tokens)
    words = sorted({m.group(0).lower() for m in found})
    return {
        "span": (s, e), "shown": (start, end),
        "segments": segments(text, start, end, found),
        "words": words, "reason": WORDS_AND_MEANING if words else MEANING,
        # "…" only where words were left out, not where whitespace was.
        "cut_before": bool(text[:start].strip()),
        "cut_after": bool(text[end:].strip()),
    }


def annotate(index, embedder, query: str, hits: list[dict],
             texts: list[str]) -> bool:
    """Give the first ``MAX_IDS`` hits their closest passage and reason.

    ``hits`` are the console's result rows, in order; ``texts`` their stored
    texts. Sets ``passage`` and ``reden`` on the rows it can explain and leaves
    the rest on today's fragment. Returns True when the passages are
    unavailable (the index read or the second embedding failed, for any
    reason) so the page can say so. The rows stay: the search succeeded.
    """
    shown = list(zip(hits, texts))[:MAX_IDS]
    if embedder is None:              # keyword search: no question vector
        for hit, _text in shown:
            hit["reden"] = WORDS
        return False
    spans = {hit["id"]: split_spans(text or "") for hit, text in shown}
    asked = [h["id"] for h, _t in shown if 0 < len(spans[h["id"]]) <= MAX_PASSAGES]
    if not asked:
        return False
    try:
        # hybrid_search embeds the question and keeps the vector to itself;
        # changing what it returns would touch the module that orders the hits.
        # The same bounded retry as there (hybrid.py), for the same reason.
        query_vector = retry_transient(lambda: embedder.embed([query])[0],
                                       settings.retry_attempts,
                                       settings.retry_base_delay,
                                       what="passage_query_embed")
        vectors = index.passages_of(asked)
    except Exception as exc:          # a 429, a 503, a timeout: all the same here
        log.warning("passages unavailable: %s", type(exc).__name__)
        return True
    other_dim = failed = 0
    for hit, text in shown:
        found = vectors.get(hit["id"]) or [] if hit["id"] in asked else []
        try:
            other_dim += any(len(v) != len(query_vector) for v in found)
            passage = best(text, found, query_vector, query, spans[hit["id"]])
        except Exception:             # one malformed vector costs one hit
            failed, passage = failed + 1, None
        if passage is not None:
            hit["passage"], hit["reden"] = passage, passage["reason"]
    if other_dim:
        log.warning("passage vectors of another dimension than the question's"
                    " for %d hit(s)", other_dim)
    if failed:
        log.warning("passage not determined for %d hit(s): malformed vectors", failed)
    return False
