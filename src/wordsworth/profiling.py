"""Born-digital detection: real logic (pypdf). It MEASURES, it does not extract.

Counts extractable characters per page and classifies against a threshold. A
parser crash is a hard error (ProfilingError -> FAILED), never a silent fallback
to unprocessable_ocr. The raw metric is returned for the audit payload so a
later threshold change re-classifies from audit data, without re-parsing."""
from __future__ import annotations

import io
from typing import Any

from pypdf import PdfReader


class ProfilingError(Exception):
    """Raised when the PDF cannot be parsed at all (distinct from 'no text')."""


def profile_pdf(data: bytes, threshold_chars_per_page: int) -> dict[str, Any]:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = len(reader.pages)
        chars = 0
        for page in reader.pages:
            chars += len((page.extract_text() or "").strip())
    except Exception as exc:  # pypdf raises a family of errors; all are hard fails
        raise ProfilingError(str(exc)) from exc

    born_digital = pages > 0 and chars >= threshold_chars_per_page * pages
    # Only integers in the payload -> stable JSONB round-trip for hashing.
    return {
        "chars": chars,
        "pages": pages,
        "bytes": len(data),
        "born_digital": born_digital,
    }
