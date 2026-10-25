# SPDX-License-Identifier: MIT
"""The one PDF extraction (design.md: "One text, by construction") and its
space insertion. Pure — no DB."""
from __future__ import annotations

import io
import re

import pypdf
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table

from wordsworth.extraction import extract_text
from wordsworth.pdf_boxes import build_box_map
from wordsworth.pdf_text import TEXT_SOURCE, page_chars, positioned_text
from wordsworth.profiling import profile_pdf


def _pdf(draw) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    draw(c)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_text_source_constant_is_pdfium_v1():
    assert TEXT_SOURCE == "pdfium-v1"


def test_profile_extract_and_box_share_one_text():
    """Profiling, extraction and the box map all read `positioned_text`
    (design.md: "One text, by construction") — none of them re-derives its
    own, differently-whitespaced text from the same bytes."""
    pdf = _pdf(lambda c: c.drawString(72, 800, "Aanvrager Jansen woont hier."))
    metric = profile_pdf(pdf, 10)
    text = extract_text(pdf)
    assert metric["chars"] == len(text.strip())
    boxes = build_box_map(pdf, "Aanvrager [PERSON:aaaaaaaa] woont hier.",
                          [("[PERSON:aaaaaaaa]", "Jansen")])
    assert len(boxes) == 1


def _no_space_pdf(first: str, second: str, gap: int) -> bytes:
    """A single text-show operator with a kerning displacement between
    ``first`` and ``second`` that pdfium itself still does not treat as a
    word gap (the cause (a) bug this change fixes) -- unlike two separate
    ``Tj`` runs, which pdfium always space-separates on its own. ``gap``
    (e.g. -135) is a raw TJ displacement, found empirically for this font/
    size to sit just inside pdfium's own threshold while clearing ordinary
    letter-to-letter kerning (see `pdf_text._GAP_FRACTION`)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica", 12)
    c._code.append(
        f"BT /F1 12 Tf 72 800 Td [({first}) {gap} ({second})] TJ ET")
    c.showPage()
    c.save()
    return buf.getvalue()


def test_pdfium_itself_emits_no_space_in_the_fixture():
    """Guards the fixture: without the fix, pdfium's own text has the two
    words run together."""
    pdf = _no_space_pdf("Jan", "aansen", -135)
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    page = doc[0]
    tp = page.get_textpage()
    raw = tp.get_text_range(0, tp.count_chars())
    tp.close()
    page.close()
    doc.close()
    assert raw == "Janaansen"


def test_words_pdfium_joins_get_a_space():
    pdf = _no_space_pdf("Jan", "aansen", -135)
    text = positioned_text(pdf)
    assert re.search(r"\baansen\b", text)


def test_the_inserted_space_has_no_char_box():
    pdf = _no_space_pdf("Jan", "aansen", -135)
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    page = doc[0]
    tp = page.get_textpage()
    chars = page_chars(tp)
    tp.close()
    page.close()
    doc.close()
    inserted = [c for c in chars if c.char == " " and c.rect is None]
    assert len(inserted) == 1
    assert "".join(c.char for c in chars) == "Jan aansen"


def test_value_found_whole_word_once_space_is_inserted():
    pdf = _no_space_pdf("Jan", "aansen", -135)
    boxes = build_box_map(pdf, "[PERSON:aaaaaaaa]",
                          [("[PERSON:aaaaaaaa]", "aansen")])
    assert len(boxes) == 1
    assert boxes[0].token == "[PERSON:aaaaaaaa]"


def test_pypdf_joins_cells_the_new_text_does_not():
    """pypdf strings table cells together with a bare newline where pdfium
    joins the same row with a space (design.md, cause (b)): a value read off
    the pypdf text ("Waarde" directly followed by "15") is a literal string
    that never occurs in the positioned text, because the two extractors
    order and join this cell boundary differently. Every value the new,
    single extraction actually produces is still located in it (one text,
    by construction)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf)
    doc.build([Table([["Datum", "Waarde"], ["15", "oktober"]])])
    pdf = buf.getvalue()

    pypdf_text = pypdf.PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "Waarde\n15" in pypdf_text  # the cell boundary pypdf does not see

    positioned = positioned_text(pdf)
    assert "Waarde\n15" not in positioned  # pdfium never produced this string

    # What the new extraction actually holds locates whole-word, unconditionally.
    boxes = build_box_map(pdf, "[DATE_MONTH:bbbbbbbb]",
                          [("[DATE_MONTH:bbbbbbbb]", "oktober")])
    assert {b.token for b in boxes} == {"[DATE_MONTH:bbbbbbbb]"}
