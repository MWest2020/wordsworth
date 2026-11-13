# SPDX-License-Identifier: MIT
"""The count-only check, as a pure function (reanonymise-particle-name-documents).

No database: `compare` reads two texts and returns numbers. The database side
-- that `reprocess.one` reads the stored text and logs after the commit -- is in
`test_reprocess_counts_db.py`.
"""
from __future__ import annotations

import json
import logging
import re

from wordsworth import reprocess_counts
from wordsworth.reprocess_counts import FIELDS, compare

P1, P2, P3 = "[PERSON:aaaaaaa1]", "[PERSON:bbbbbbb2]", "[PERSON:ccccccc3]"
B1 = "[BSN:ddddddd4]"
L1 = "[LOCATION:eeeeeee5]"


def _row(before, after, added, removed):
    return {"before": before, "after": after, "added": added, "removed": removed}


def test_a_type_that_grows():
    uit = compare(f"{P1} sprak met iemand", f"{P1} sprak met {P2}")
    assert uit == {"PERSON": _row(1, 2, 1, 0)}


def test_a_type_that_shrinks():
    uit = compare(f"{P1} en {P2} bij {L1}", f"{P1} en iemand bij {L1}")
    assert uit["PERSON"] == _row(2, 1, 0, 1)
    assert uit["LOCATION"] == _row(1, 1, 0, 0)


def test_a_replaced_token_shows_as_added_one_removed_one():
    """De zaak waarvoor dit bestaat: de voornaam was een eigen token, na de
    regel is de hele naam met partikel één token. Het totaal blijft gelijk;
    alleen added/removed laten zien dat er iets veranderde."""
    uit = compare(f"{P1} ter Braak, {P2}", f"{P3}, {P2}")
    assert uit["PERSON"] == _row(2, 2, 1, 1)


def test_a_token_five_times_counts_once():
    tekst = " en ".join([P1] * 5)
    uit = compare(tekst, tekst + f" {B1}")
    assert uit["PERSON"] == _row(1, 1, 0, 0)
    assert uit["BSN"] == _row(0, 1, 1, 0)


def test_a_type_that_disappears_is_still_reported():
    assert compare(f"{B1}", "geen tokens meer") == {"BSN": _row(1, 0, 0, 1)}


def test_no_tokens_no_types():
    """Irreversibele modus: kale `[BSN]`-plaatshouders zijn geen pseudoniemen,
    dus de check vindt niets -- en zegt dat ook, met een lege dict."""
    assert compare("[BSN] en [PERSON]", "[BSN] en [PERSON]") == {}
    assert compare("", "") == {}


def test_the_answer_holds_no_token():
    uit = compare(f"{P1} {B1}", f"{P2} {B1}")
    assert not re.search(r"[0-9a-f]{8}", json.dumps(uit))
    for per_type in uit.values():
        assert tuple(per_type) == FIELDS
        assert all(isinstance(v, int) for v in per_type.values())


def test_the_log_line_is_id_types_and_numbers(caplog):
    caplog.set_level(logging.INFO, logger="wordsworth.pipeline")
    counts = compare(f"{P1} ter Braak", f"{P3}")
    line = reprocess_counts.log("0b1e5c2a-0000-4000-8000-000000000001", counts)

    assert line in caplog.text
    parsed = json.loads(line)
    assert set(parsed) == {"event", "document_id", "counts", "level"}
    assert parsed["event"] == "reprocess_counts"
    assert parsed["counts"] == {"PERSON": _row(1, 1, 1, 1)}
    for verboden in ("ter Braak", "aaaaaaa1", "ccccccc3", "[PERSON:"):
        assert verboden not in caplog.text
