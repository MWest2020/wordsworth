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
    boxes = build_box_map(pdf, "Aanvrager [PERSON:aaaaaaaa] woont hier.",
                          [("[PERSON:aaaaaaaa]", "Jansen")])
    assert len(boxes) == 1
    assert boxes[0].page == 0
    assert boxes[0].token == "[PERSON:aaaaaaaa]"
    r = boxes[0].rect
    assert r.x0 < r.x1 and r.y0 < r.y1


def test_box_map_holds_no_value():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Aanvrager Jansen woont hier."))
    boxes = build_box_map(pdf, "Aanvrager [PERSON:aaaaaaaa] woont hier.",
                          [("[PERSON:aaaaaaaa]", "Jansen")])
    for b in boxes:
        assert "Jansen" not in repr(b)
        assert set(vars(b.rect)) == {"x0", "y0", "x1", "y1"}


def test_two_line_name_gives_two_rectangles():
    pdf = _pdf(lambda c: (
        c.drawString(72, 800, "Aanvrager Jan"),
        c.drawString(72, 786, "sen woont hier"),
    ))
    # Detection ran over the positioned text with the line break still in it
    # (pdf_text.py), so the value it found literally contains that break.
    boxes = build_box_map(pdf, "Aanvrager [PERSON:aaaaaaaa] woont hier",
                          [("[PERSON:aaaaaaaa]", "Jan\nsen")])
    assert len(boxes) == 2
    assert {b.page for b in boxes} == {0}
    assert {b.token for b in boxes} == {"[PERSON:aaaaaaaa]"}
    # The two rects sit on two different lines (y ranges do not overlap).
    r1, r2 = boxes[0].rect, boxes[1].rect
    assert r1.y1 <= r2.y0 or r2.y1 <= r1.y0


def test_value_at_end_of_line_is_located_with_no_box_for_the_space():
    # "2022" ends one line, "Gemeente" starts the next, with no space drawn
    # between them -- dropping the line break used to glue them into one
    # word and fail the whole-word check (proposal.md, cause 1).
    pdf = _pdf(lambda c: (
        c.drawString(72, 800, "Jaar 2022"),
        c.drawString(72, 786, "Gemeente Utrecht"),
    ))
    boxes = build_box_map(pdf, "Jaar [DATE_TIME:aaaaaaaa] Gemeente Utrecht",
                          [("[DATE_TIME:aaaaaaaa]", "2022")])
    assert len(boxes) == 1
    assert boxes[0].rect.x0 < boxes[0].rect.x1


def test_person_stored_in_a_different_case_is_located():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Aanvrager JANSEN woont hier."))
    boxes = build_box_map(pdf, "Aanvrager [PERSON:aaaaaaaa] woont hier.",
                          [("[PERSON:aaaaaaaa]", "jansen")])
    assert len(boxes) == 1


def test_postcode_spaced_differently_is_located():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Postcode 1234 AB hier."))
    boxes = build_box_map(pdf, "Postcode [POSTCODE:aaaaaaaa] hier.",
                          [("[POSTCODE:aaaaaaaa]", "1234AB")])
    assert len(boxes) == 1


def test_a_type_outside_the_rule_still_matches_exactly():
    # IBAN is not in the normalisation rule table (default rule: case kept
    # as-is) -- unlike PERSON/POSTCODE, a case mismatch must still miss.
    pdf = _pdf(lambda c: c.drawString(72, 800, "IBAN nl91abna0417164300 hier."))
    with pytest.raises(ValueNotLocatedError):
        build_box_map(pdf, "IBAN [IBAN:aaaaaaaa] hier.",
                      [("[IBAN:aaaaaaaa]", "NL91ABNA0417164300")])


def test_value_not_located_fails_hard_with_no_partial_box_map():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Jansen is hier."))
    # The anonymised text claims two occurrences of the token; the PDF
    # itself only has the value once.
    anonymized = "[PERSON:aaaaaaaa] is hier. [PERSON:aaaaaaaa] weer."
    with pytest.raises(ValueNotLocatedError) as exc_info:
        build_box_map(pdf, anonymized, [("[PERSON:aaaaaaaa]", "Jansen")])
    exc = exc_info.value
    assert exc.token == "[PERSON:aaaaaaaa]"
    assert exc.in_anonymized == 2
    assert exc.in_positioned == 1
    assert "Jansen" not in str(exc)  # never the value, only counts


def test_absent_value_locates_nothing_without_raising():
    pdf = _pdf(lambda c: c.drawString(72, 800, "Niets bijzonders hier."))
    boxes = build_box_map(pdf, "Niets bijzonders hier.", [("[EMAIL:bbbbbbbb]", "x@y.nl")])
    assert boxes == []
