"""Whole-word locating of redaction values in the PDF's positioned text
(pypdfium2), never by character offsets (design.md). Pure — no DB."""
from __future__ import annotations

import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from wordsworth.pdf_boxes import ValueNotLocatedError, build_box_map


def _pdf(draw) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    draw(c)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_single_value_gets_one_box_on_its_page():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Aanvrager Jansen woont hier."))
    boxes = build_box_map(pdf, "Aanvrager Jansen woont hier.",
                          [("[PERSON:aaaaaaaa]", "Jansen")])
    assert len(boxes) == 1
    assert boxes[0].page == 0
    assert boxes[0].token == "[PERSON:aaaaaaaa]"
    r = boxes[0].rect
    assert r.x0 < r.x1 and r.y0 < r.y1


def test_box_map_holds_no_value():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Aanvrager Jansen woont hier."))
    boxes = build_box_map(pdf, "Aanvrager Jansen woont hier.",
                          [("[PERSON:aaaaaaaa]", "Jansen")])
    for b in boxes:
        assert "Jansen" not in repr(b)
        assert set(vars(b.rect)) == {"x0", "y0", "x1", "y1"}


def test_two_line_name_gives_two_rectangles():
    pdf = _pdf(lambda c: (
        c.drawString(72, 800, "Aanvrager Jan"),
        c.drawString(72, 786, "sen woont hier"),
    ))
    boxes = build_box_map(pdf, "Aanvrager Jansen woont hier",
                          [("[PERSON:aaaaaaaa]", "Jansen")])
    assert len(boxes) == 2
    assert {b.page for b in boxes} == {0}
    assert {b.token for b in boxes} == {"[PERSON:aaaaaaaa]"}
    # The two rects sit on two different lines (y ranges do not overlap).
    r1, r2 = boxes[0].rect, boxes[1].rect
    assert r1.y1 <= r2.y0 or r2.y1 <= r1.y0


def test_value_not_located_fails_hard_with_no_partial_box_map():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Jansen is hier."))
    # pypdf_text claims two occurrences; the PDF itself has only one.
    with pytest.raises(ValueNotLocatedError) as exc_info:
        build_box_map(pdf, "Jansen is hier. Jansen weer.",
                      [("[PERSON:aaaaaaaa]", "Jansen")])
    exc = exc_info.value
    assert exc.token == "[PERSON:aaaaaaaa]"
    assert exc.in_pypdf == 2
    assert exc.in_positioned == 1
    assert "Jansen" not in str(exc)  # never the value, only counts


def test_absent_value_locates_nothing_without_raising():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Niets bijzonders hier."))
    boxes = build_box_map(pdf, "Niets bijzonders hier.", [("[EMAIL:bbbbbbbb]", "x@y.nl")])
    assert boxes == []
