# SPDX-License-Identifier: MIT
"""Writing the long-corpus PDF and rasterising its scanned pages
(synthetic-long-corpus, design.md: "Scanned pages").

Two passes. First every page is written as ordinary vector text (reportlab).
Then the PDF is rebuilt: scanned pages are replaced by a raster of themselves
(the same path `pdf_render.py` uses to rasterise a page -- `page.render` ->
`to_pil()` -> JPEG through a `BytesIO` `ImageReader` -> `drawImage`, never a
bare PIL image, which makes reportlab re-flate the pixels), everything else is
copied through unchanged via `pypdf`. A scanned page therefore has no text
layer at all: `wordsworth.pdf_text.page_text` reads it as empty.

Determinism: every canvas is built with `invariant=1` (reportlab's own
mechanism -- it fixes `/CreationDate` and `/ID` to a constant instead of the
wall clock) and the final writer's metadata is stamped with that same fixed
date explicitly, since `pypdf` does not carry `/Info` over when it repacks
pages. The raster bytes themselves depend on the installed pypdfium2/Pillow
build, not on this module.
"""
from __future__ import annotations

import io

import pypdf
import pypdfium2 as pdfium
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .synthetic import Document

DPI = 200
_SCALE = DPI / 72
_JPEG_QUALITY = 80
_MARGIN = 72
_LEADING = 14
# Not Helvetica: its digit kerning (e.g. "11") produces a gap up to 0.424x the
# character height for some pairs, above `pdf_text._GAP_FRACTION` (0.4) --
# `page_text` would then insert a space inside a BSN, splitting it. Times-Roman
# measured worst case (digit/letter pairs in BSN/IBAN/phone/email/doc-number
# values) is 0.321, comfortably under the gate.
_FONT = ("Times-Roman", 10)

# reportlab's `invariant=1` resolves to this timestamp (2000-01-01 UTC); set
# explicitly on the final writer too, since pypdf does not copy `/Info` when
# repacking pages.
_CREATION_DATE = "D:20000101000000+00'00'"
_METADATA = {
    "/Author": "wordsworth",
    "/Title": "SYNTHETISCH",
    "/Subject": "synthetic-long-corpus",
    "/Creator": "wordsworth",
    "/CreationDate": _CREATION_DATE,
    "/ModDate": _CREATION_DATE,
}


def _draw_page(c: canvas.Canvas, text: str) -> None:
    c.setFont(*_FONT)
    y = A4[1] - _MARGIN
    for line in text.split("\n"):
        c.drawString(_MARGIN, y, line)
        y -= _LEADING
    c.showPage()


def _text_pdf(pages: list[Document]) -> bytes:
    """Pass 1: every page as vector text, nothing rasterised yet."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1)
    c.setAuthor(_METADATA["/Author"])
    c.setTitle(_METADATA["/Title"])
    c.setSubject(_METADATA["/Subject"])
    c.setCreator(_METADATA["/Creator"])
    for page in pages:
        _draw_page(c, page.text)
    c.save()
    return buf.getvalue()

def _rasterise(pdf_bytes: bytes, index: int, size: tuple[float, float]) -> bytes:
    """One page of `pdf_bytes`, rendered at `DPI` and re-embedded as the only
    content of a fresh one-page PDF -- no text layer survives."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[index]
        bitmap = page.render(scale=_SCALE)
        image = bitmap.to_pil().convert("RGB")
        page.close()
    finally:
        pdf.close()
    jpeg = io.BytesIO()
    image.save(jpeg, format="JPEG", quality=_JPEG_QUALITY)
    jpeg.seek(0)
    width, height = size
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height), invariant=1)
    c.drawImage(ImageReader(jpeg), 0, 0, width=width, height=height)
    c.showPage()
    c.save()
    return buf.getvalue()


def write_pdf(pages: list[Document], scanned: set[int]) -> bytes:
    """The final PDF: `pages` in order, each page rendered as vector text
    except the 1-indexed page numbers in `scanned`, which are rasterised and
    carry no text layer. Reproducible for a fixed input on a fixed
    pypdfium2/Pillow build."""
    text_pdf = _text_pdf(pages)
    reader = pypdf.PdfReader(io.BytesIO(text_pdf))
    writer = pypdf.PdfWriter()
    for i, page in enumerate(reader.pages):
        if (i + 1) in scanned:
            size = (float(page.mediabox.width), float(page.mediabox.height))
            raster = _rasterise(text_pdf, i, size)
            writer.add_page(pypdf.PdfReader(io.BytesIO(raster)).pages[0])
        else:
            writer.add_page(page)
    writer.add_metadata(_METADATA)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
