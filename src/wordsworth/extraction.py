"""Real text extraction (pypdf). In-memory only — clear text is never persisted.

By the time a document is `extractable` it has already parsed successfully during
profiling, so extraction rarely fails; if it does, that is a loud failure
(ExtractionError -> FAILED), never a silent skip."""
from __future__ import annotations

import io

from pypdf import PdfReader


class ExtractionError(Exception):
    """Raised when text cannot be pulled from the PDF."""


def extract_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise ExtractionError(str(exc)) from exc
