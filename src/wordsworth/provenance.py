"""Validation for `/ingest`'s optional `source_url` and `fetched_at`.

One rule, defined once, so the API's 400 and any future caller agree on it
rather than guessing it twice. Neither field is required (an unpublished
document has no URL); a malformed value is rejected with the reason, never
silently dropped.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

MAX_SOURCE_URL_LENGTH = 2048


class ProvenanceError(ValueError):
    """A malformed `source_url` or `fetched_at`; the message is the 400 reason."""


def validate_source_url(source_url: str) -> str:
    if len(source_url) > MAX_SOURCE_URL_LENGTH:
        raise ProvenanceError(
            f"source_url exceeds {MAX_SOURCE_URL_LENGTH} characters")
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ProvenanceError("source_url must be https:// with a host")
    return source_url


def parse_fetched_at(fetched_at: str) -> datetime:
    try:
        value = datetime.fromisoformat(fetched_at)
    except ValueError as exc:
        raise ProvenanceError("fetched_at must be ISO-8601") from exc
    if value.tzinfo is None:
        raise ProvenanceError("fetched_at must include a timezone")
    return value
