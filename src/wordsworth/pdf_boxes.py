# SPDX-License-Identifier: MIT
"""Locate redaction values whole-word in the PDF's own positioned text
(pypdfium2), never by character offsets from the pypdf text (design.md):
the two extractors order and whitespace text differently, so an offset from
one does not land on the right place in the other.

pypdfium2 inserts ``\\r\\n`` between lines it detects by layout, which breaks a
literal match of a value that wraps across two lines. We therefore search a
per-page copy of the text with line breaks removed (keeping an index back to
the real character array), then split the matched characters back into
per-line rectangles by where their vertical position jumps. A merge that joins
two unrelated words at a page's line boundary can only ever cause a MISSED
match (the trailing/leading word character fails the match's own word-boundary
check) — never a wrong one; a miss is exactly what the fail-hard count check
below is for.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pypdfium2 as pdfium


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
    """A value occurs fewer times in the positioned text than in the pypdf
    text — some occurrence cannot be boxed. Carries counts only, never the
    value (null-vector rule: no partial box map, ever)."""

    def __init__(self, token: str, in_pypdf: int, in_positioned: int):
        super().__init__(
            f"{token}: located {in_positioned} of {in_pypdf} occurrence(s)")
        self.token = token
        self.in_pypdf = in_pypdf
        self.in_positioned = in_positioned


def _whole_word(value: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)")


def count_whole_word(text: str, value: str) -> int:
    return len(_whole_word(value).findall(text))


def _flatten(text: str) -> tuple[str, list[int]]:
    """``text`` with every ``\\r``/``\\n`` dropped, plus the index back to the
    original character array for every character that survives."""
    out: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        if ch in "\r\n":
            continue
        out.append(ch)
        index.append(i)
    return "".join(out), index


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
    pdf_bytes: bytes, pypdf_text: str, items: list[tuple[str, str]],
) -> list[Box]:
    """The box map for ``items`` (``(token, clear_value)`` pairs) against
    ``pdf_bytes``. ``pypdf_text`` is the SAME text the anonymizer ran over
    (joined across pages, as ``extraction.extract_text`` produces it) — the
    fail-hard occurrence count is taken against it, never against the
    positioned text itself.

    Raises :class:`ValueNotLocatedError` on the first value located fewer
    times than it occurs in ``pypdf_text`` — no partial box map is ever
    returned."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        # Keep every page and textpage open for the whole call: closing a page
        # invalidates its textpage's underlying handle in pdfium.
        page_data = []  # (flat_text, index_map, page, textpage) per page
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            n = textpage.count_chars()
            raw = textpage.get_text_range(0, n) if n else ""
            flat, index_map = _flatten(raw)
            page_data.append((flat, index_map, page, textpage))

        boxes: list[Box] = []
        try:
            for token, value in items:
                if not value:
                    continue
                expected = count_whole_word(pypdf_text, value)
                pattern = _whole_word(value)
                found = 0
                for page_index, (flat, index_map, _page, textpage) in enumerate(page_data):
                    for m in pattern.finditer(flat):
                        found += 1
                        orig = index_map[m.start():m.end()]
                        char_boxes = [Rect(*textpage.get_charbox(idx)) for idx in orig]
                        for group in _line_groups(char_boxes):
                            boxes.append(Box(page_index, _merge(group), token))
                if found < expected:
                    raise ValueNotLocatedError(token, expected, found)
        finally:
            for _, _, page, textpage in page_data:
                textpage.close()
                page.close()
        return boxes
    finally:
        pdf.close()
