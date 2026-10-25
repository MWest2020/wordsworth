"""Real text extraction: `positioned_text` (pypdfium2, pdf-redaction-locate).
In-memory only — clear text is never persisted.

By the time a document is `extractable` it has already parsed successfully during
profiling, so extraction rarely fails; if it does, that is a loud failure
(ExtractionError -> FAILED), never a silent skip."""
from __future__ import annotations

from .pdf_text import positioned_text


class ExtractionError(Exception):
    """Raised when text cannot be pulled from the PDF."""


def extract_text(data: bytes) -> str:
    try:
        return positioned_text(data)
    except Exception as exc:
        raise ExtractionError(str(exc)) from exc
