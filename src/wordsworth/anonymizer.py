"""The anonymization seam (driver/protocol pattern) and the interim driver.

The pipeline depends on the ``Anonymizer`` protocol, never on a concrete engine,
so OpenAnonymiser can be dropped in as a second driver without pipeline changes.
Replacement is irreversible: placeholders carry no mapping back to the original.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from . import detectors
from .detection_stats import DETERMINISTIC, DetectionStats


@dataclass
class AnonymizationResult:
    text: str  # PII irreversibly replaced with typed placeholders
    counts: dict[str, int]  # {"email": n, "iban": n, "bsn": n}
    # Per-layer aggregates (add-detection-confidence): {layer: {TYPE: {count,
    # min_score, max_score, below_threshold}}} — never values or offsets.
    detections: dict = field(default_factory=dict)
    # add-detection-feedback: content hash of the allow/deny lists in force
    # (None = none configured), so the audit record pins the rule version.
    lists_hash: str | None = None


@runtime_checkable
class Anonymizer(Protocol):
    def anonymize(self, text: str) -> AnonymizationResult: ...


class DeterministicAnonymizer:
    """Interim driver: high-precision deterministic PII only (BSN, IBAN, email),
    replaced irreversibly with typed placeholders."""

    def anonymize(self, text: str) -> AnonymizationResult:
        counts: dict[str, int] = {}
        stats = DetectionStats()
        for label, pattern, validate in detectors.DETECTORS:
            text, counts[label] = detectors.substitute(
                text, pattern, lambda v, label=label: f"[{label.upper()}]", validate
            )
            stats.add(DETERMINISTIC, label, 1.0, counts[label])  # validated = certain
        return AnonymizationResult(text=text, counts=counts, detections=stats.to_dict())
