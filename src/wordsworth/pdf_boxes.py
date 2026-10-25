# SPDX-License-Identifier: MIT
"""Locate redaction values whole-word in the PDF's own positioned text
(pypdfium2, `pdf_text.positioned_text`), never by character offsets (design.md):
detection runs over this same text, by construction (pdf-redaction-locate), so
a value that was found once exists here to be found again.

pypdfium2 inserts ``\\r\\n`` between lines it detects by layout, which breaks a
literal match of a value that wraps across two lines. We therefore search a
per-page copy of the text with every run of ``\\r``/``\\n`` collapsed to one
space (keeping each surviving character's box, or ``None`` for a space —
this one or one `pdf_text.page_chars` inserted), and match a value's words
with optional whitespace between them, then split the matched characters
back into per-line rectangles by where their vertical position jumps. A
value is matched the way its PII type is normalised: case-insensitively for
the casefold types, whitespace-insensitively for POSTCODE, exactly
otherwise (pdf-redaction-match).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pypdfium2 as pdfium

from .normalization import RULES, _casefold, _postcode
from .pdf_text import Char, page_chars
from .pseudonymizer import label_of


@dataclass(frozen=True)
class Rect:
    """A rectangle in PDF canvas units (points), origin bottom-left — the same
    space pypdfium2's ``get_charbox`` and reportlab's canvas both use."""

    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Box:
    """One redaction rectangle: which page, where, and the pseudonym token it
    covers. Holds no value — see the box map's persistence contract."""

    page: int
    rect: Rect
    token: str


class ValueNotLocatedError(Exception):
    """A token occurs more often in the anonymised text than its value can be
    found, whole-word, in the positioned text — some occurrence cannot be
    boxed. Carries counts only, never the value (null-vector rule: no partial
    box map, ever)."""

    def __init__(self, token: str, in_anonymized: int, in_positioned: int):
        super().__init__(
            f"{token}: located {in_positioned} of {in_anonymized} occurrence(s)")
        self.token = token
        self.in_anonymized = in_anonymized
        self.in_positioned = in_positioned


def _whole_word(value: str, *, flags: int = 0, whitespace_insensitive: bool = False) -> re.Pattern[str]:
    """A whole-word pattern for ``value``. Its words (split on whitespace) are
    joined with ``\\s*``, so a value detected across a line break — where
    ``_flatten`` leaves a single space or nothing — still matches.
    ``whitespace_insensitive`` additionally makes every whitespace position
    INSIDE a word optional (POSTCODE: normalisation strips whitespace
    everywhere, not only between words)."""
    if whitespace_insensitive:
        body = r"\s*".join(re.escape(c) for c in value if not c.isspace())
    else:
        body = r"\s*".join(re.escape(w) for w in value.split())
    return re.compile(r"(?<!\w)" + body + r"(?!\w)", flags)


def _flatten(chars: list[Char]) -> tuple[str, list[tuple[float, float, float, float] | None]]:
    """``chars`` with every RUN of ``\\r``/``\\n`` collapsed to one space: the
    text to search, plus each surviving character's box (``None`` for a
    space — either this one or one `page_chars` inserted — nothing is drawn
    for it on its own). A line break thus acts as a word separator, never
    joining the last word of a line to the first word of the next."""
    text: list[str] = []
    rects: list[tuple[float, float, float, float] | None] = []
    in_break = False
    for c in chars:
        if c.char in "\r\n":
            if not in_break:
                text.append(" ")
                rects.append(None)
                in_break = True
            continue
        in_break = False
        text.append(c.char)
        rects.append(c.rect)
    return "".join(text), rects


def _line_groups(boxes: list[Rect]) -> list[list[Rect]]:
    """Split consecutive char boxes into per-line runs: a new run starts when
    the vertical center jumps by more than half a character's height."""
    groups: list[list[Rect]] = []
    for box in boxes:
        if groups:
            prev = groups[-1][-1]
            prev_mid = (prev.y0 + prev.y1) / 2
            mid = (box.y0 + box.y1) / 2
            height = max(prev.y1 - prev.y0, box.y1 - box.y0, 1.0)
            if abs(mid - prev_mid) <= height / 2:
                groups[-1].append(box)
                continue
        groups.append([box])
    return groups


def _merge(boxes: list[Rect]) -> Rect:
    return Rect(
        min(b.x0 for b in boxes), min(b.y0 for b in boxes),
        max(b.x1 for b in boxes), max(b.y1 for b in boxes),
    )


def build_box_map(
    pdf_bytes: bytes, anonymized_text: str, items: list[tuple[str, str]],
) -> list[Box]:
    """The box map for ``items`` (``(token, clear_value)`` pairs) against
    ``pdf_bytes``. ``anonymized_text`` is the text the anonymizer PRODUCED —
    the count check (design.md) is: a token's literal count there must be at
    most its value's whole-word match count in the PDF's own positioned text
    (``pdf_text.positioned_text``, built per page via ``page_chars`` here, so
    the two never disagree about where a character sits or whether a space
    was inserted between two of pdfium's).

    Raises :class:`ValueNotLocatedError` on the first token located fewer
    times than it occurs in ``anonymized_text`` — no partial box map is ever
    returned."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page_data = []  # (flat_text, rects) per page
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            try:
                page_data.append(_flatten(page_chars(textpage)))
            finally:
                textpage.close()
                page.close()

        boxes: list[Box] = []
        for token, value in items:
            if not value:
                continue
            expected = anonymized_text.count(token)
            rule = RULES.get(label_of(token))
            pattern = _whole_word(
                value, flags=re.IGNORECASE if rule is _casefold else 0,
                whitespace_insensitive=rule is _postcode)
            found = 0
            for page_index, (flat, rects) in enumerate(page_data):
                for m in pattern.finditer(flat):
                    found += 1
                    char_boxes = [Rect(*r) for r in rects[m.start():m.end()]
                                 if r is not None]
                    for group in _line_groups(char_boxes):
                        boxes.append(Box(page_index, _merge(group), token))
            if found < expected:
                raise ValueNotLocatedError(token, expected, found)
        return boxes
    finally:
        pdf.close()
