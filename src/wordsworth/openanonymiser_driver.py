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

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

import httpx

from .anonymizer import AnonymizationResult, DeterministicAnonymizer
from .concurrency import limiter
from .config import settings
from .detection_stats import OPENANONYMISER, DetectionStats


class AnonymizationEngineError(RuntimeError):
    """The anonymization engine failed. Deliberately carries no document text."""


class _EngineFn(Protocol):
    """(redacted text, counts[, per-layer detection aggregates]). The third
    element is optional so a plain 2-tuple test double still satisfies it."""
    def __call__(self, text: str) -> tuple: ...


@dataclass(frozen=True)
class Entity:
    """A detected entity span: its type and the substring at [start, end)."""
    entity_type: str
    text: str
    start: int
    end: int
    # add-detection-confidence: which layer found it, how confidently (0..1).
    layer: str = OPENANONYMISER
    score: float = 1.0


def _score(e: dict) -> float:
    """The service's confidence; its absence is a contract break → hard error
    (no silent default), per the no-silent-fallback rule."""
    if "score" not in e:
        raise AnonymizationEngineError("OpenAnonymiser entity without score")
    return float(e["score"])


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


def _redact_one(text: str) -> tuple[str, dict[str, int], dict]:
    """One anonymize call for one text segment; returns (redacted, counts,
    per-layer detection aggregates).

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
    stats = DetectionStats(settings.detection_min_score)
    for entity in data.get("entities_found") or []:  # what the service detected
        score = _score(entity)  # hard error without one
        label = str(entity["entity_type"]).lower()
        counts[label] = counts.get(label, 0) + 1
        stats.add(OPENANONYMISER, label, score)  # aggregates only, no value/span
    return data["anonymized_text"], counts, stats.to_dict()


def _openanonymiser_redact(text: str) -> tuple[str, dict[str, int], dict]:
    """Redact entity PII via the OpenAnonymiser GLiNER service; return
    (redacted text, counts, per-layer detection aggregates).

    Long documents are split into bounded chunks and redacted per chunk, then
    reassembled (the ``replace`` strategy leaves non-entity text unchanged, so
    the pieces concatenate faithfully) with counts summed. This keeps each GLiNER
    call short enough that its attention memory cannot OOM the service — even a
    generous memory limit was not enough for whole-document calls.

    A document's chunks are mutually independent, so they are dispatched
    concurrently (bounded by ``anonymize_concurrency``, the same cap the
    process-wide ``limiter`` enforces) and load-balanced across the OpenAnonymiser
    replicas by the Service — turning a serial N×latency wait into ~N/concurrency.
    Results are reassembled in chunk order, so the concatenation is unchanged. If
    any chunk fails, the exception propagates (the caller turns it into a hard
    ``AnonymizationEngineError`` — no partial, un-redacted text is ever emitted)."""
    chunks = _chunk_text(text, settings.anonymize_chunk_chars)
    if len(chunks) == 1:
        return _redact_one(text)
    workers = max(1, min(len(chunks), settings.anonymize_concurrency))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # map preserves input order; the first raised exception propagates.
        results = list(pool.map(_redact_one, chunks))
    parts: list[str] = []
    counts: dict[str, int] = {}
    stats = DetectionStats(settings.detection_min_score)
    for redacted, c, *agg in results:  # a 2-tuple double carries no aggregates
        parts.append(redacted)
        for label, n in c.items():
            counts[label] = counts.get(label, 0) + n
        if agg:
            stats.merge(agg[0])
    return "".join(parts), counts, stats.to_dict()


def _detect_one(text: str) -> list[Entity]:
    """Detect entity spans in one segment via the OpenAnonymiser service. Reuses
    the ``anonymize`` endpoint but keeps only ``entities_found`` (type + span);
    the redacted text is discarded, because the reversible driver substitutes its
    own keyed tokens. Offsets are relative to ``text``."""
    url = settings.openanonymiser_url.rstrip("/") + "/api/v1/anonymize"
    with limiter("anonymize", settings.anonymize_concurrency):
        response = httpx.post(
            url,
            json={"text": text, "language": "nl",
                  "anonymization_strategy": "replace"},
            timeout=settings.openanonymiser_timeout,
        )
    response.raise_for_status()
    out: list[Entity] = []
    for e in response.json().get("entities_found") or []:
        score = _score(e)  # contract check first: no score is a hard error
        if "start" not in e or "end" not in e:
            continue  # no span → cannot substitute reversibly; skip defensively
        out.append(Entity(str(e["entity_type"]), str(e.get("text", "")),
                          int(e["start"]), int(e["end"]), OPENANONYMISER, score))
    return out


def detect_entities(text: str) -> list[Entity]:
    """Default detection engine: chunk (bounding GLiNER memory), detect each chunk
    concurrently across the replicas, and return entities with offsets mapped back
    to the whole ``text``. A chunk failure propagates (fail-hard at the caller)."""
    chunks = _chunk_text(text, settings.anonymize_chunk_chars)
    if len(chunks) == 1:
        return _detect_one(text)
    bases: list[int] = []
    base = 0
    for chunk in chunks:                       # _chunk_text is lossless, so the
        bases.append(base)                     # base offsets rebuild global spans
        base += len(chunk)
    workers = max(1, min(len(chunks), settings.anonymize_concurrency))

    def one(indexed: tuple[int, str]) -> list[Entity]:
        i, chunk = indexed
        off = bases[i]
        return [Entity(e.entity_type, e.text, e.start + off, e.end + off,
                       e.layer, e.score)
                for e in _detect_one(chunk)]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        per_chunk = list(pool.map(one, enumerate(chunks)))
    return [e for sub in per_chunk for e in sub]


class OpenAnonymiserAnonymizer:
    """``Anonymizer`` driver delegating to the OpenAnonymiser service, composed
    with the deterministic detectors. Construction is cheap; no service call
    happens until :meth:`anonymize`."""

    def __init__(self, engine: _EngineFn | None = None, lists=None) -> None:
        # ``engine`` is a test seam only; the default is the real HTTP client.
        self._engine = engine or _openanonymiser_redact
        self._deterministic = DeterministicAnonymizer()
        # add-detection-feedback: only the DENY list applies here — the service
        # redacts server-side, so an allow-list cannot un-redact its output. The
        # reversible driver applies both.
        from .detection_lists import DetectionLists

        self._lists = lists or DetectionLists()

    def _apply_deny(self, text: str, stats: DetectionStats) -> str:
        for t, pats in self._lists.deny.items():
            for p in pats:
                text, n = p.subn(f"[{t}]", text)
                stats.add("list", t, 1.0, n)
        return text

    def anonymize(self, text: str) -> AnonymizationResult:
        deterministic = self._deterministic.anonymize(text)
        pre = DetectionStats(settings.detection_min_score)
        pre.merge(deterministic.detections)
        deterministic.text = self._apply_deny(deterministic.text, pre)  # deny list
        deterministic.detections = pre.to_dict()
        deterministic.lists_hash = self._lists.hash
        if not deterministic.text.strip():
            # Nothing left for the entity engine; the service rejects empty text
            # (422). Structured-PII counts (all zeros here) still stand.
            return deterministic
        try:
            redacted, engine_counts, *agg = self._engine(deterministic.text)
        except Exception as exc:
            # Hard error, no pass-through: the un-redacted text never leaves
            # this frame, and the raised error carries none of it.
            raise AnonymizationEngineError(
                "OpenAnonymiser engine failed; refusing to emit un-redacted text"
            ) from exc
        counts = dict(deterministic.counts)  # keep zeros: detectors did run
        for label, n in engine_counts.items():
            counts[label] = counts.get(label, 0) + n
        # Per-layer aggregates: deterministic layer + (when the engine reports
        # them) the OpenAnonymiser layer. A 2-tuple engine (test double) yields
        # deterministic-only aggregates — never an empty record.
        stats = DetectionStats(settings.detection_min_score)
        stats.merge(deterministic.detections)
        if agg:
            stats.merge(agg[0])
        return AnonymizationResult(text=redacted, counts=counts,
                                   detections=stats.to_dict(),
                                   lists_hash=self._lists.hash)
