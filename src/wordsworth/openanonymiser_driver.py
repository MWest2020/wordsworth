"""OpenAnonymiser-backed driver behind the ``Anonymizer`` seam.

Composite: the deterministic detectors run FIRST (audited structured-PII
precision — BSN elfproef, IBAN mod-97, email), then the OpenAnonymiser GLiNER
service redacts entity PII such as personal names. Counts are merged per type
into one ``AnonymizationResult``.

Architecture A (2026-08): the engine is an HTTP client to the OpenAnonymiser
service, NOT in-process inference. The heavy ML (torch + spaCy + GLiNER) runs
co-located with the service — on alma, reached at ``WORDSWORTH_OPENANONYMISER_URL``
(in-cluster svc-DNS). Wordsworth pulls no torch/spaCy/presidio of its own.

Invariants: replacement is irreversible (typed placeholders, no mapping); a
service failure raises ``AnonymizationEngineError`` — un-redacted text is never
passed through (no silent fallbacks; fail-hard when the service is unreachable).
"""
from __future__ import annotations

from typing import Protocol

import httpx

from .anonymizer import AnonymizationResult, DeterministicAnonymizer
from .concurrency import limiter
from .config import settings


class AnonymizationEngineError(RuntimeError):
    """The anonymization engine failed. Deliberately carries no document text."""


class _EngineFn(Protocol):
    def __call__(self, text: str) -> tuple[str, dict[str, int]]: ...


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split into pieces of ≤ max_chars that concatenate back to the original
    exactly (splits on line boundaries; a single over-long line is hard-split).
    Bounds the sequence length sent to GLiNER so its O(n^2) attention cannot
    spike memory / OOM on long documents."""
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    cur = ""
    for line in text.splitlines(keepends=True):
        if cur and len(cur) + len(line) > max_chars:
            chunks.append(cur)
            cur = ""
        cur += line
        while len(cur) > max_chars:            # a single very long line
            chunks.append(cur[:max_chars])
            cur = cur[max_chars:]
    if cur:
        chunks.append(cur)
    return chunks


def _redact_one(text: str) -> tuple[str, dict[str, int]]:
    """One anonymize call for one text segment; returns (redacted, counts).

    POSTs to ``{WORDSWORTH_OPENANONYMISER_URL}/api/v1/anonymize`` with the
    ``replace`` strategy (Presidio ``<ENTITY_TYPE>`` placeholders). Any transport
    error or non-2xx response raises — the caller turns that into a hard error
    rather than emitting un-redacted text. Concurrency is bounded (ADR-0001)."""
    url = settings.openanonymiser_url.rstrip("/") + "/api/v1/anonymize"
    with limiter("anonymize", settings.anonymize_concurrency):
        response = httpx.post(
            url,
            json={"text": text, "language": "nl",
                  "anonymization_strategy": "replace"},
            timeout=settings.openanonymiser_timeout,
        )
    response.raise_for_status()
    data = response.json()
    counts: dict[str, int] = {}
    for entity in data.get("entities_found") or []:  # what the service detected
        label = str(entity["entity_type"]).lower()
        counts[label] = counts.get(label, 0) + 1
    return data["anonymized_text"], counts


def _openanonymiser_redact(text: str) -> tuple[str, dict[str, int]]:
    """Redact entity PII via the OpenAnonymiser GLiNER service; return
    (redacted text, counts).

    Long documents are split into bounded chunks and redacted per chunk, then
    reassembled (the ``replace`` strategy leaves non-entity text unchanged, so
    the pieces concatenate faithfully) with counts summed. This keeps each GLiNER
    call short enough that its attention memory cannot OOM the service — even a
    generous memory limit was not enough for whole-document calls."""
    chunks = _chunk_text(text, settings.anonymize_chunk_chars)
    if len(chunks) == 1:
        return _redact_one(text)
    parts: list[str] = []
    counts: dict[str, int] = {}
    for chunk in chunks:
        redacted, c = _redact_one(chunk)
        parts.append(redacted)
        for label, n in c.items():
            counts[label] = counts.get(label, 0) + n
    return "".join(parts), counts


class OpenAnonymiserAnonymizer:
    """``Anonymizer`` driver delegating to the OpenAnonymiser service, composed
    with the deterministic detectors. Construction is cheap; no service call
    happens until :meth:`anonymize`."""

    def __init__(self, engine: _EngineFn | None = None) -> None:
        # ``engine`` is a test seam only; the default is the real HTTP client.
        self._engine = engine or _openanonymiser_redact
        self._deterministic = DeterministicAnonymizer()

    def anonymize(self, text: str) -> AnonymizationResult:
        deterministic = self._deterministic.anonymize(text)
        if not deterministic.text.strip():
            # Nothing left for the entity engine; the service rejects empty text
            # (422). Structured-PII counts (all zeros here) still stand.
            return deterministic
        try:
            redacted, engine_counts = self._engine(deterministic.text)
        except Exception as exc:
            # Hard error, no pass-through: the un-redacted text never leaves
            # this frame, and the raised error carries none of it.
            raise AnonymizationEngineError(
                "OpenAnonymiser engine failed; refusing to emit un-redacted text"
            ) from exc
        counts = dict(deterministic.counts)  # keep zeros: detectors did run
        for label, n in engine_counts.items():
            counts[label] = counts.get(label, 0) + n
        return AnonymizationResult(text=redacted, counts=counts)
