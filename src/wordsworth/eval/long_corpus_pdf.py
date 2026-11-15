# SPDX-License-Identifier: MIT
"""Draw a long-corpus document's pages and rasterise the scanned ones
(long_corpus_parts.py builds the content; long_corpus.py assembles pages and
the gold; this module only draws).

Two passes per document: `render_source_pdf` draws every page as vector text
-- this is what the gold is read back from -- and `render_final_pdf` redraws
the same pages, except a chosen few, which it rasterises from the source
(pdfium, as `pdf_render.py` does) and embeds as an image with no text layer.
Redrawing vector pages a second time, rather than copying them, keeps both
passes built from the one `Document` per page and therefore byte-identical
given the same input (reproducibility; `Canvas(..., invariant=1)` removes the
wall-clock `/CreationDate` and `/ID` that would otherwise differ run to run).
"""
from __future__ import annotations

import io

import pypdfium2 as pdfium
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

_MARGIN_X = 50
_TOP_Y = 812
_BOTTOM_Y = 30
_LINE_HEIGHT = 14
_FONT = "Helvetica"
_FONT_SIZE = 10
_TABLE_X_OFFSETS = (0, 150, 300, 420)

_AUTHOR = "wordsworth-synthetic"
_CREATOR = "wordsworth"
_SUBJECT = "synthetic long corpus (synthetic-long-corpus)"

# JPEG, not FlateDecode: a flate-compressed raster at this DPI is how one
# document once came out at 151 MB (pdf_render.py's RENDER_VERSION note).
_SCAN_DPI = 200
_JPEG_QUALITY = 80


def _new_canvas(buf: io.BytesIO, title: str) -> canvas.Canvas:
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    c.setAuthor(_AUTHOR)
    c.setTitle(title)
    c.setSubject(_SUBJECT)
    c.setCreator(_CREATOR)
    return c


def _draw_page(c: canvas.Canvas, text: str) -> None:
    """One `drawString` per line, one more per tab-separated cell -- every
    planted value is drawn whole, in a single run (long_corpus_parts.py)."""
    c.setPageSize(A4)
    c.setFont(_FONT, _FONT_SIZE)
    y = _TOP_Y
    for line in text.split("\n"):
        if y < _BOTTOM_Y:
            break
        cells = line.split("\t")
        if len(cells) == 1:
            c.drawString(_MARGIN_X, y, line)
        else:
            for i, cell in enumerate(cells):
                x = _MARGIN_X + _TABLE_X_OFFSETS[min(i, len(_TABLE_X_OFFSETS) - 1)]
                c.drawString(x, y, cell)
        y -= _LINE_HEIGHT


def render_source_pdf(title: str, page_docs: list) -> bytes:
    """Every page as vector text -- the version the gold is read back from."""
    buf = io.BytesIO()
    c = _new_canvas(buf, title)
    for doc in page_docs:
        _draw_page(c, doc.text)
        c.showPage()
    c.save()
    return buf.getvalue()


def _rasterize(source_bytes: bytes, index: int):
    pdf = pdfium.PdfDocument(source_bytes)
    try:
        page = pdf[index]
        try:
            bitmap = page.render(scale=_SCAN_DPI / 72)
            image = bitmap.to_pil().convert("RGB")
            return image, page.get_size()
        finally:
            page.close()
    finally:
        pdf.close()


def render_final_pdf(title: str, page_docs: list, source_bytes: bytes,
                      scanned_pages: list[int]) -> bytes:
    """Redraw every page; a page number in `scanned_pages` (1-indexed) is
    rasterised from `source_bytes` and embedded as an image instead -- no
    text layer, so it is lost to anything that reads text, not pixels."""
    scanned_idx = {p - 1 for p in scanned_pages}
    buf = io.BytesIO()
    c = _new_canvas(buf, title)
    for i, doc in enumerate(page_docs):
        if i in scanned_idx:
            image, (width, height) = _rasterize(source_bytes, i)
            img_buf = io.BytesIO()
            image.save(img_buf, format="JPEG", quality=_JPEG_QUALITY)
            img_buf.seek(0)
            c.setPageSize((width, height))
            c.drawImage(ImageReader(img_buf), 0, 0, width=width, height=height)
        else:
            _draw_page(c, doc.text)
        c.showPage()
    c.save()
    return buf.getvalue()
