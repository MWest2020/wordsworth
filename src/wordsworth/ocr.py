"""The OCR seam (driver/protocol pattern) and its local engine.

The pipeline depends on the ``OcrEngine`` protocol, never on a concrete engine,
so the recovery step (pipeline.recover) can be tested with a double and the real
engine swapped without pipeline changes. Local OCR only — no cloud in the
critical path. A failed OCR is a HARD error (OcrError): loud and retryable,
never a silent skip that would drop a scanned document from the corpus."""
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
    def ocr(self, pdf_bytes: bytes) -> str: ...


class TesseractEngine:
    """Local OCR via ocrmypdf + tesseract (Dutch model). No cloud, no network.

    ocrmypdf rasterises and OCRs the image-only PDF, writing the recovered plain
    text to a sidecar file. The toolchain import and invocation are lazy: the
    born-digital path never needs OCR, and any failure surfaces as OcrError.
    """

    def __init__(self, lang: str = "nld"):
        self.lang = lang

    @classmethod
    def from_config(cls) -> "TesseractEngine":
        return cls(settings.ocr_language)

    def ocr(self, pdf_bytes: bytes) -> str:
        try:
            import ocrmypdf
        except Exception as exc:  # missing toolchain is a hard error, not a skip
            raise OcrError(f"ocr toolchain unavailable: {exc}") from exc
        with tempfile.TemporaryDirectory() as d:
            src, out, sidecar = (os.path.join(d, n) for n in ("in.pdf", "out.pdf", "out.txt"))
            with open(src, "wb") as fh:
                fh.write(pdf_bytes)
            try:
                ocrmypdf.ocr(
                    src, out, language=self.lang, sidecar=sidecar,
                    force_ocr=True, progress_bar=False,
                )
                with open(sidecar, encoding="utf-8") as fh:
                    return fh.read()
            except Exception as exc:  # any ocrmypdf/tesseract failure is loud
                raise OcrError(f"ocr failed: {exc}") from exc


class FixedOcrEngine:
    """Test double: returns preset text. No model, no binary, no network."""

    def __init__(self, text: str, lang: str = "nld"):
        self._text = text
        self.lang = lang

    def ocr(self, pdf_bytes: bytes) -> str:
        return self._text
