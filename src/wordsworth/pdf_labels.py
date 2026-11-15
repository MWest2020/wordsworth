# SPDX-License-Identifier: MIT
"""The typed label on a redaction box (`[PERSOON 1]`): white vector text on the
black box, so a reader sees what kind of value was removed, and search/copy
find the label where the value was.

Three things make it legible, and each was once missing (#448):

- **Fill mode.** The text render mode is part of the PDF graphics state and
  outlives the text object that set it. The invisible text layer
  (`pdf_render._draw_invisible_layer`) sets mode 3 and did not set it back, so
  the labels drawn after it were in the file, findable, and invisible on every
  box. The layer now ends in mode 0; reportlab only writes a mode *change*, so
  asking for mode 0 here would write nothing and guard nothing.
- **It fits the box.** The size follows the box height, then shrinks until the
  label is no wider than the box: white text past the edge of a black box is
  white on the page, which reads as a label cut off mid-word.
- **Nothing outside the box.** Below `_MIN_PT` a label is not readable anyway,
  so it stops shrinking there and is clipped to its box instead.
"""
from __future__ import annotations

from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .pdf_boxes import Box, Rect

_FONT = "Helvetica"
_LABEL_RGB = (1, 1, 1)
_MIN_PT = 4.0
_MAX_PT = 10.0
_PAD = 1.0  # points between the box edge and the label, left and right


def label_size(rect: Rect, label: str) -> float:
    """The font size for ``label`` on ``rect``: 80% of the box height, at most
    ``_MAX_PT``, smaller when the label would be wider than the box, never
    under ``_MIN_PT``."""
    size = min((rect.y1 - rect.y0) * 0.8, _MAX_PT)
    width = stringWidth(label, _FONT, size)
    room = max((rect.x1 - rect.x0) - 2 * _PAD, 0.0)
    if width > room:
        size *= room / width
    return max(_MIN_PT, size)


def draw_labels(c: canvas.Canvas, boxes: list[Box], labels: dict[str, str]) -> None:
    for b in boxes:
        r = b.rect
        label = labels.get(b.token, b.token)
        size = label_size(r, label)
        c.saveState()
        clip = c.beginPath()
        clip.rect(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0)
        c.clipPath(clip, stroke=0, fill=0)
        t = c.beginText()
        t.setFillColorRGB(*_LABEL_RGB)
        t.setFont(_FONT, size)
        # Helvetica's cap height is ~0.72 em: centre the capitals on the box.
        t.setTextOrigin(r.x0 + _PAD, r.y0 + ((r.y1 - r.y0) - 0.72 * size) / 2)
        t.textOut(label)
        c.drawText(t)
        c.restoreState()
