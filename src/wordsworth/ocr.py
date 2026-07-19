"""The OCR seam (driver/protocol pattern) and its local engine.

The pipeline depends on the ``OcrEngine`` protocol, never on a concrete engine,
so the recovery step (recovery.recover) can be tested with a double and the real
engine swapped without pipeline changes. Local OCR only — no cloud in the
critical path. An engine returns a TEXT-LAYER PDF (the scanned PDF with a
searchable text layer added), never raw text: a recovered document must flow
through the ordinary profile_pdf/extract_text (pypdf) path unchanged. A failed
OCR is a HARD error (OcrError): loud and retryable, never a silent skip that
would drop a scanned document from the corpus."""
from __future__ import annotations

import os
import tempfile
from typing import Protocol, runtime_checkable

from .config import settings


class OcrError(Exception):
    """Raised when OCR cannot be produced. Loud + retryable; never a silent skip."""


@runtime_checkable
class OcrEngine(Protocol):
    lang: str
    def ocr(self, pdf_bytes: bytes) -> bytes: ...


class TesseractEngine:
    """Local OCR via ocrmypdf + tesseract (Dutch model). No cloud, no network.

    ocrmypdf rasterises and OCRs the image-only PDF and writes a searchable PDF
    (`out.pdf`) whose text layer pypdf can extract; those bytes are the result.
    The toolchain import and invocation are lazy: the born-digital path never
    needs OCR, and any failure surfaces as OcrError.
    """

    def __init__(self, lang: str = "nld"):
        self.lang = lang

    @classmethod
    def from_config(cls) -> "TesseractEngine":
        return cls(settings.ocr_language)

    def ocr(self, pdf_bytes: bytes) -> bytes:
        try:
            import ocrmypdf
        except Exception as exc:  # missing toolchain is a hard error, not a skip
            raise OcrError(f"ocr toolchain unavailable: {exc}") from exc
        with tempfile.TemporaryDirectory() as d:
            src, out = (os.path.join(d, n) for n in ("in.pdf", "out.pdf"))
            with open(src, "wb") as fh:
                fh.write(pdf_bytes)
            try:
                ocrmypdf.ocr(
                    src, out, language=self.lang,
                    force_ocr=True, progress_bar=False,
                )
                with open(out, "rb") as fh:
                    return fh.read()
            except Exception as exc:  # any ocrmypdf/tesseract failure is loud
                raise OcrError(f"ocr failed: {exc}") from exc


class FixedOcrEngine:
    """Test double: renders the preset text into a real text-layer PDF
    (reportlab, dev-only, imported lazily). No OCR model, no binary, no network —
    but the output honours the contract: PDF bytes whose text layer pypdf reads.
    """

    def __init__(self, text: str, lang: str = "nld"):
        self._text = text
        self.lang = lang

    def ocr(self, pdf_bytes: bytes) -> bytes:
        import io

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(72, 800, self._text)
        c.showPage()
        c.save()
        return buf.getvalue()
