# SPDX-License-Identifier: MIT
"""Reading the passage vectors of the hits on a search page.

`SearchIndex.passages_of` lives on both drivers; its body lives here, so the
rule they share is written once: at most ``MAX_IDS`` ids, and one log line per
read (change search-matching-passage).

Why a limit in the read and not only in the caller: the console takes a
``size`` from the URL, so "the hits on the page" is not ten by itself. A passage
vector is 1024 numbers (bge-m3), about 20 kB as JSON, and a long document has
some 80 passages (about 1.6 MB) -- ten such documents are an estimated 16 MB
per page. The read refuses more ids instead of trusting every caller to
remember; the console also leaves out a document of more than 200 passages
(`console_passage.MAX_PASSAGES`).

The log line carries counts and milliseconds, never an id or a text: it exists
to measure the payload on the real index (the estimate above is not a
measurement), and a document id next to a query time says more than it needs to.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable

log = logging.getLogger("wordsworth.search")

#: The most ids one read may ask for: the first ten hits on a page.
MAX_IDS = 10

Vectors = dict[str, list[list[float]]]


def read(fetch: Callable[[list[str]], Vectors], ids, driver: str) -> Vectors:
    """Run ``fetch`` over ``ids`` under the shared rule.

    Raises ``ValueError`` for more than ``MAX_IDS`` ids, before anything is
    read. An id without passages is absent from the answer or has an empty
    list; the caller treats both as "no passage to show".
    """
    ids = [str(i) for i in ids]
    if len(ids) > MAX_IDS:
        raise ValueError(f"passages_of reads at most {MAX_IDS} ids, not {len(ids)}")
    began = time.perf_counter()
    found = fetch(ids) if ids else {}
    log.info(json.dumps({
        "event": "passages_read", "driver": driver, "ids": len(ids),
        "passages": sum(len(v) for v in found.values()),
        # The numbers that crossed the wire; their JSON size is roughly 20
        # bytes each. The response's own size is not measurable here: the
        # client hands back a parsed dict, without the raw body or its length.
        "floats": sum(len(p) for v in found.values() for p in v),
        "bytes": "unknown",
        "ms": round((time.perf_counter() - began) * 1000, 1),
    }))
    return found


def mget(client, index: str, ids: list[str]) -> Vectors:
    """The OpenSearch half: one ``mget`` for the passage vectors only.

    ``_source`` is narrowed to ``passages.vector``: the text and the document
    vector are not needed here, and the page is heavy enough without them.
    """
    docs = client.mget(body={"ids": ids}, index=index,
                       _source=["passages.vector"])["docs"]
    out: Vectors = {}
    for d in docs:
        if not d.get("found"):
            continue
        passages = (d.get("_source") or {}).get("passages") or []
        if isinstance(passages, dict):      # one passage, written as an object
            passages = [passages]
        out[d["_id"]] = [p["vector"] for p in passages if p.get("vector")]
    return out
