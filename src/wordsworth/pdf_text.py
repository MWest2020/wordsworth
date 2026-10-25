# SPDX-License-Identifier: MIT
"""The one PDF text extraction (design.md: "One text, by construction").

Detection finds values in a text; `pdf_boxes` locates them again in the same
PDF's positioned text. Two different extractors order and whitespace a page
differently, so a value the first found can be missing, whole, from the
second -- that was the root cause this change fixes, not a `\\s*` patch.
`positioned_text` is therefore the SINGLE PDF extraction: profiling
(born-digital detection), the anonymize step, `DocumentText`, the index text
and the box map all read it, with `text_source` ``pdfium-v1``.

pdfium itself sometimes emits no space between two words it renders as
separate text-showing operators (cause (a) of the bug this change fixes). A
space is inserted here wherever two characters on one line sit further apart
than a fixed fraction of the character height and pdfium emitted none --
`page_chars` is the shared primitive, so `pdf_boxes.build_box_map` sees
exactly the same inserted spaces and the same positions as this text. An
inserted space carries no character box (`rect is None`): nothing is drawn
for it on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

import pypdfium2 as pdfium

#: Recorded on the anonymize/reanonymize audit record and compared by the
#: backfill (reversible-backfill.md) against documents processed before this
#: change.
TEXT_SOURCE = "pdfium-v1"

# The fraction of character height beyond which a horizontal gap between two
# characters on one line counts as a missing word space. Not decided by the
# proposal (open question); the hard gate -- detection run over the pilot set
# plus gooise-meren-woo-2022, pdfium vs this value -- is what checks it.
#
# 0.4 is chosen with a real document's worth of margin either side, measured
# on this PoC's PDF-generation path (Helvetica via reportlab): ordinary
# kerning inside a BSN/IBAN/email line peaks at ~0.33 (digit-to-digit is the
# tightest), and a constructed gap pdfium itself still reads as one word
# reaches ~0.43. A value nearer either edge risks splitting a real BSN
# (false insertion -- a detector never sees the digits as one token) or
# missing a genuine joined word (the bug this change fixes); the hard gate's
# PERSON/BSN aggregate-count comparison on real documents is what actually
# settles it.
_GAP_FRACTION = 0.4

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class Char:
    """One character of a page's text, in reading order. ``rect`` is the
    pdfium charbox (x0, y0, x1, y1), or ``None`` for a space this module
    inserted -- there is no glyph, so no box exists to draw."""

    char: str
    rect: Rect | None


# A tight charbox thinner or narrower than this is degenerate. Real documents
# have it: Word-exported Woo PDFs of the Gooise Meren dossier gave a tight box
# 0.01 pt high for every character (2026-10-26), and a redaction box built
# from those covered nothing -- the "redacted" PDF showed every name.
_DEGENERATE_PT = 0.5


def char_box(textpage, index: int) -> Rect:
    """The box of one character: pdfium's tight box, or its loose box (the
    font's full bounds) when the tight one is degenerate. The one place every
    caller takes a character's box from -- text, box map and render must agree
    on where a glyph is, or the text layer and the paint disagree."""
    x0, y0, x1, y1 = textpage.get_charbox(index)
    if (y1 - y0) < _DEGENERATE_PT or (x1 - x0) <= 0:
        x0, y0, x1, y1 = textpage.get_charbox(index, loose=True)
    return (x0, y0, x1, y1)


def _needs_space(prev_rect: Rect, rect: Rect) -> bool:
    height = max(prev_rect[3] - prev_rect[1], rect[3] - rect[1], 1.0)
    gap = rect[0] - prev_rect[2]
    return gap > height * _GAP_FRACTION


def page_chars(textpage) -> list[Char]:
    """Every character pypdfium2 reports for one page's textpage, with a
    virtual space inserted wherever two glyphs on the same line sit too far
    apart and pdfium emitted none between them (see module docstring).

    A newline pdfium emits between lines it detects by layout resets the gap
    check -- a line break is never mistaken for a missing word space."""
    n = textpage.count_chars()
    raw = textpage.get_text_range(0, n) if n else ""
    chars: list[Char] = []
    prev_rect: Rect | None = None
    for i, ch in enumerate(raw):
        if ch in "\r\n":
            chars.append(Char(ch, None))
            prev_rect = None
            continue
        rect = char_box(textpage, i)
        if prev_rect is not None and ch != " " and _needs_space(prev_rect, rect):
            chars.append(Char(" ", None))
        chars.append(Char(ch, rect))
        prev_rect = None if ch == " " else rect
    return chars


def page_text(textpage) -> str:
    """One page's text, built from `page_chars` (inserted spaces included)."""
    return "".join(c.char for c in page_chars(textpage))


def positioned_text(pdf_bytes: bytes) -> str:
    """The document's text, pages joined by a newline, exactly as every other
    PDF-reading step in wordsworth sees it. ``text_source`` is ``pdfium-v1``."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        pages = []
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            try:
                pages.append(page_text(textpage))
            finally:
                textpage.close()
                page.close()
        return "\n".join(pages)
    finally:
        pdf.close()
