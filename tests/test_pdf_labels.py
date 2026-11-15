# SPDX-License-Identifier: MIT
"""The label on a redaction box can be read at 100% zoom (#448). Pure -- no DB.

The other render tests read the text layer, and the label was in it all along:
it was drawn in the invisible text mode the layer before it had left behind.
So these look at pixels, at the 96 dpi a browser shows a PDF in at 100%."""
from __future__ import annotations

import io
import re

import pypdf
import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from wordsworth.pdf_boxes import Rect, build_box_map
from wordsworth.pdf_labels import label_size
from wordsworth.pdf_render import render

NAME, POSTCODE = "Jansen", "6601 AB"
LINE = f"Aanvrager {NAME} woont op postcode {POSTCODE} te Wijchen."
ITEMS = [("[PERSON:aaaaaaaa]", NAME), ("[POSTCODE:cccccccc]", POSTCODE)]
LABELS = {"[PERSON:aaaaaaaa]": "[PERSOON 1]", "[POSTCODE:cccccccc]": "[POSTCODE 1]"}
ZOOM_100 = 96 / 72


def _redacted(labels=LABELS):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 800, LINE)
    c.showPage()
    c.save()
    boxes = build_box_map(buf.getvalue(), LINE, ITEMS)
    return render(buf.getvalue(), boxes, labels), boxes


def _pixels(out: bytes, rect: Rect, grow: float = 0.0) -> list[tuple[int, int, int]]:
    """The pixels of ``rect`` (widened by ``grow`` points to the right) at 100%."""
    pdf = pdfium.PdfDocument(out)
    page = pdf[0]
    height = page.get_height()
    image = page.render(scale=ZOOM_100).to_pil().convert("RGB")
    page.close()
    pdf.close()
    return [image.getpixel((x, y))
            for x in range(round(rect.x0 * ZOOM_100) + 1, round((rect.x1 + grow) * ZOOM_100))
            for y in range(round((height - rect.y1) * ZOOM_100) + 1,
                           round((height - rect.y0) * ZOOM_100))]


def test_the_label_shows_as_light_text_on_every_box_at_100_percent():
    out, boxes = _redacted()
    assert len(boxes) == 2
    for b in boxes:
        pixels = _pixels(out, b.rect)
        light = [p for p in pixels if min(p) >= 160]
        dark = [p for p in pixels if max(p) <= 60]
        assert len(light) >= 8, f"no visible label on the box for {b.token}"
        assert len(dark) > len(light)          # still a black box, with text on it


def test_a_box_without_label_text_stays_black():
    """The control for the test above: what it counts is the label, not the page."""
    out, boxes = _redacted({t: " " for t in LABELS})
    for b in boxes:
        assert not [p for p in _pixels(out, b.rect) if min(p) >= 160]


def test_the_text_is_drawn_in_fill_mode_after_the_invisible_layer():
    out, _ = _redacted()
    # `3 Tr` is the invisible layer; whatever follows it must be back at 0.
    stream = pypdf.PdfReader(io.BytesIO(out)).pages[0].get_contents().get_data().decode("latin-1")
    for label in LABELS.values():
        before = stream[:stream.index(f"({label})")]
        assert re.findall(r"\b(\d) Tr\b", before)[-1] == "0"


def test_a_label_wider_than_its_box_shrinks_to_fit():
    _, boxes = _redacted()
    box = next(b for b in boxes if b.token.startswith("[POSTCODE"))
    label = LABELS[box.token]
    size = label_size(box.rect, label)
    assert 4.0 <= size < (box.rect.y1 - box.rect.y0) * 0.8
    assert stringWidth(label, "Helvetica", size) <= box.rect.x1 - box.rect.x0


@pytest.mark.parametrize("width, expected", [(200.0, 8.0), (2.0, 4.0)])
def test_the_size_follows_the_height_and_has_a_floor(width, expected):
    assert label_size(Rect(0, 0, width, 10.0), "[PERSOON 1]") == pytest.approx(expected)


def test_a_label_that_cannot_fit_does_not_spill_past_its_box():
    """`J.` is narrower than any readable `[PERSOON 1]`: clipped, not smeared
    over the text that follows."""
    line = "Aanvrager J. woont te Wijchen."
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 800, line)
    c.showPage()
    c.save()
    boxes = build_box_map(buf.getvalue(), line, [("[PERSON:aaaaaaaa]", "J.")])
    plain = render(buf.getvalue(), boxes, {"[PERSON:aaaaaaaa]": " "})
    labelled = render(buf.getvalue(), boxes, LABELS)
    r = boxes[0].rect
    beside = Rect(r.x1 + 1, r.y0, r.x1 + 40, r.y1)
    assert _pixels(labelled, beside) == _pixels(plain, beside)
