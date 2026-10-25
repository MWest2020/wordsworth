"""Rasterise, paint, rebuild (design.md: "Rendering"). Pure — no DB."""
from __future__ import annotations

import io
import shutil

import pypdf
import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from wordsworth.pdf_boxes import build_box_map
from wordsworth.pdf_render import render

NAME = "Jansen"
BSN = "123456782"
LINE = f"Aanvrager {NAME} woont in Naarden, BSN {BSN}."
LABELS = {"[PERSON:aaaaaaaa]": "[PERSOON 1]", "[BSN:bbbbbbbb]": "[BSN 1]"}
ITEMS = [("[PERSON:aaaaaaaa]", NAME), ("[BSN:bbbbbbbb]", BSN)]


def _source_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("A source title that must not survive")
    c.setAuthor("Jan Jansen")
    c.setFont("Helvetica", 12)
    c.drawString(72, 800, LINE)
    c.showPage()
    c.save()
    return buf.getvalue()


def _redacted() -> tuple[bytes, list]:
    source = _source_pdf()
    boxes = build_box_map(source, LINE, ITEMS)
    return render(source, boxes, LABELS), boxes


def test_name_and_bsn_gone_from_text_layer_pypdf():
    out, _ = _redacted()
    text = pypdf.PdfReader(io.BytesIO(out)).pages[0].extract_text()
    assert NAME not in text
    assert BSN not in text
    assert "[PERSOON 1]" in text
    assert "[BSN 1]" in text


def test_name_and_bsn_gone_from_text_layer_pdfium():
    out, _ = _redacted()
    pdf = pdfium.PdfDocument(out)
    page = pdf[0]
    tp = page.get_textpage()
    text = tp.get_text_range(0, tp.count_chars())
    tp.close()
    page.close()
    pdf.close()
    assert NAME not in text
    assert BSN not in text


def test_source_character_boxes_lie_inside_the_rects():
    source = _source_pdf()
    boxes = build_box_map(source, LINE, ITEMS)
    pdf = pdfium.PdfDocument(source)
    page = pdf[0]
    tp = page.get_textpage()
    n = tp.count_chars()
    text = tp.get_text_range(0, n)
    for name, value in (("[PERSON:aaaaaaaa]", NAME), ("[BSN:bbbbbbbb]", BSN)):
        start = text.index(value)
        for i in range(start, start + len(value)):
            cx0, cy0, cx1, cy1 = tp.get_charbox(i)
            rects = [b.rect for b in boxes if b.token == name]
            assert any(r.x0 - 0.5 <= cx0 and cx1 <= r.x1 + 0.5
                      and r.y0 - 0.5 <= cy0 and cy1 <= r.y1 + 0.5 for r in rects)
    tp.close()
    page.close()
    pdf.close()


def test_pixels_under_the_box_are_the_box_colour():
    out, boxes = _redacted()
    pdf = pdfium.PdfDocument(out)
    page = pdf[0]
    height = page.get_height()
    scale = 300 / 72
    image = page.render(scale=scale).to_pil().convert("RGB")
    for b in boxes:
        r = b.rect
        cx = int(((r.x0 + r.x1) / 2) * scale)
        cy = int((height - (r.y0 + r.y1) / 2) * scale)
        assert image.getpixel((cx, cy)) == (0, 0, 0)
    page.close()
    pdf.close()


def test_label_is_placed_on_its_box():
    out, boxes = _redacted()
    pdf = pdfium.PdfDocument(out)
    page = pdf[0]
    tp = page.get_textpage()
    n = tp.count_chars()
    text = tp.get_text_range(0, n)
    for label in ("[PERSOON 1]", "[BSN 1]"):
        i = text.index(label)
        cx0, cy0, cx1, cy1 = tp.get_charbox(i)
        box = next(b for b in boxes
                  if LABELS[b.token] == label)
        r = box.rect
        mid_x = (cx0 + cx1) / 2
        mid_y = (cy0 + cy1) / 2
        assert r.x0 - 2 <= mid_x <= r.x1 + 2
        assert r.y0 - 5 <= mid_y <= r.y1 + 5
    tp.close()
    page.close()
    pdf.close()


def test_nothing_is_carried_over_from_the_source():
    out, _ = _redacted()
    reader = pypdf.PdfReader(io.BytesIO(out))
    meta = reader.metadata or {}
    assert meta.get("/Title") != "A source title that must not survive"
    assert meta.get("/Author") != "Jan Jansen"
    assert reader.pages[0].get("/Annots") is None
    assert reader.outline == []


def test_tesseract_finds_no_name_in_the_raster():
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract not installed")
    pytesseract = pytest.importorskip("pytesseract")
    out, _ = _redacted()
    pdf = pdfium.PdfDocument(out)
    page = pdf[0]
    image = page.render(scale=300 / 72).to_pil().convert("RGB")
    page.close()
    pdf.close()

    found = pytesseract.image_to_string(image, lang="nld")
    assert NAME not in found
    assert BSN not in found
