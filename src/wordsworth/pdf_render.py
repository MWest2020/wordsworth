# SPDX-License-Identifier: MIT
"""Rasterise, paint, rebuild (design.md: "Rendering"). Nothing is copied from
the source PDF — no metadata, no annotations, no outlines — because the
output is built fresh with reportlab from a raster of the source, never from
the source document object itself.

One function (`render`) serves both the redacted and the reveal endpoint: the
caller simply omits the boxes it wants left alone. A box left out is not
painted over, and its original characters pass through the invisible text
layer unchanged — so "reveal this type" needs no separate clear-value
handling here, only a smaller box list.
"""
from __future__ import annotations

import io
from collections import defaultdict

import pypdfium2 as pdfium
from PIL import ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .pdf_boxes import Box, Rect
from .pdf_text import char_box

# A box thinner or narrower than this hides nothing at any useful zoom.
_MIN_BOX_PT = 0.5

DPI = 300
_SCALE = DPI / 72
_BOX_RGB = (0, 0, 0)
_LABEL_RGB = (1, 1, 1)

# JPEG, not FlateDecode (reportlab's default): flate barely shrinks a 300
# dpi page raster, which is why one document came out at 151 MB.
_JPEG_QUALITY = 80

# Bumped by hand with every change to this module; part of the cache key.
RENDER_VERSION = 1


def _by_page(boxes: list[Box]) -> dict[int, list[Box]]:
    out: dict[int, list[Box]] = defaultdict(list)
    for b in boxes:
        out[b.page].append(b)
    return out


def _to_pixels(rect: Rect, page_height: float) -> tuple[float, float, float, float]:
    # PDF canvas space is bottom-left origin; the raster is top-down.
    return (
        rect.x0 * _SCALE,
        (page_height - rect.y1) * _SCALE,
        rect.x1 * _SCALE,
        (page_height - rect.y0) * _SCALE,
    )


class DegenerateBoxError(ValueError):
    """A redaction box with no surface. Painting it would hide nothing while
    the PDF still claims to be redacted, so the render refuses instead."""


def _check_boxes(boxes: list[Box]) -> None:
    for b in boxes:
        if (b.rect.y1 - b.rect.y0) < _MIN_BOX_PT or (b.rect.x1 - b.rect.x0) < _MIN_BOX_PT:
            raise DegenerateBoxError(
                f"box for {b.token} on page {b.page} has no surface; rebuild the box map")


def _paint(image, boxes: list[Box], page_height: float) -> None:
    draw = ImageDraw.Draw(image)
    for b in boxes:
        draw.rectangle(_to_pixels(b.rect, page_height), fill=_BOX_RGB)


def _encode(image) -> ImageReader:
    # A file object, not a bare PIL Image, is what makes reportlab embed the
    # already-compressed bytes (DCTDecode) instead of re-flating the pixels.
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    buf.seek(0)
    return ImageReader(buf)


def _label_size(rect: Rect) -> float:
    return max(5.0, min((rect.y1 - rect.y0) * 0.8, 10.0))


def _draw_labels(c: canvas.Canvas, boxes: list[Box], labels: dict[str, str]) -> None:
    c.setFillColorRGB(*_LABEL_RGB)
    for b in boxes:
        label = labels.get(b.token, b.token)
        size = _label_size(b.rect)
        c.setFont("Helvetica", size)
        c.drawString(b.rect.x0 + 1, b.rect.y0 + (b.rect.y1 - b.rect.y0 - size) / 2 + 1,
                    label)


def _contains(rect: Rect, point_box: Rect, eps: float = 0.5) -> bool:
    cx = (point_box.x0 + point_box.x1) / 2
    cy = (point_box.y0 + point_box.y1) / 2
    return (rect.x0 - eps <= cx <= rect.x1 + eps
            and rect.y0 - eps <= cy <= rect.y1 + eps)


def _covering(boxes: list[Box], char_rect: Rect) -> Box | None:
    for b in boxes:
        if _contains(b.rect, char_rect):
            return b
    return None


def _draw_invisible_layer(c: canvas.Canvas, textpage, boxes: list[Box]) -> None:
    """Reconstruct the page's NON-redacted text as invisible (render-mode 3)
    runs, so search/copy keep working for everything the page still shows. A
    redacted span is skipped here entirely — the vector label drawn on its
    box (`_draw_labels`) is itself ordinary fill-mode text, so it already is
    the searchable/copyable replacement for that span; emitting it a second
    time here would only duplicate it.

    Consecutive non-redacted characters are grouped into one run per
    ``textOut`` call (one absolute ``Td`` per *word run*, not per character):
    positioning every single character with its own absolute move reads to a
    PDF text extractor as a run of one-character lines, which defeats the
    very search/copy continuity this layer exists for."""
    n = textpage.count_chars()
    if not n:
        return
    text = textpage.get_text_range(0, n)
    t = c.beginText()
    t.setTextRenderMode(3)  # invisible: present in the content stream only
    t.setFont("Helvetica", 8)
    run: list[str] = []
    origin: tuple[float, float] | None = None

    def flush() -> None:
        if run:
            t.setTextOrigin(*origin)
            t.textOut("".join(run))
            run.clear()

    for i, ch in enumerate(text):
        if ch in "\r\n":
            flush()
            origin = None
            continue
        char_rect = Rect(*char_box(textpage, i))
        if _covering(boxes, char_rect) is not None:
            flush()
            origin = None
            continue
        if not ch.strip():
            if run:  # whitespace inside a run keeps words separated; it never starts one
                run.append(ch)
            continue
        if origin is None:
            origin = (char_rect.x0, char_rect.y0)
        run.append(ch)
    flush()
    c.drawText(t)


def render(pdf_bytes: bytes, boxes: list[Box], labels: dict[str, str]) -> bytes:
    """Rasterise every page at 300 dpi, paint ``boxes``, JPEG-encode the
    result, and rebuild a fresh PDF with reportlab: vector labels on the
    boxes plus an invisible text layer. A box not in ``boxes`` is left
    untouched — its pixels and its original characters pass straight through
    (the reveal use)."""
    _check_boxes(boxes)  # fail closed: never a "redacted" PDF that hides nothing
    grouped = _by_page(boxes)
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.setAuthor("")
        c.setTitle("")
        c.setSubject("")
        c.setCreator("wordsworth")
        for i in range(len(pdf)):
            page = pdf[i]
            width, height = page.get_size()
            page_boxes = grouped.get(i, [])
            bitmap = page.render(scale=_SCALE)
            image = bitmap.to_pil().convert("RGB")
            _paint(image, page_boxes, height)
            c.setPageSize((width, height))
            c.drawImage(_encode(image), 0, 0, width=width, height=height)
            textpage = page.get_textpage()
            try:
                _draw_invisible_layer(c, textpage, page_boxes)
            finally:
                textpage.close()
            _draw_labels(c, page_boxes, labels)
            c.showPage()
            page.close()
        c.save()
        return buf.getvalue()
    finally:
        pdf.close()
