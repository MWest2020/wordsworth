"""The anonymization seam (driver/protocol pattern) and the interim driver.

The pipeline depends on the ``Anonymizer`` protocol, never on a concrete engine,
so OpenAnonymiser can be dropped in as a second driver without pipeline changes.
Replacement is irreversible: placeholders carry no mapping back to the original.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from . import detectors


@dataclass
class AnonymizationResult:
    text: str  # PII irreversibly replaced with typed placeholders
    counts: dict[str, int]  # {"email": n, "iban": n, "bsn": n}


@runtime_checkable
class Anonymizer(Protocol):
    def anonymize(self, text: str) -> AnonymizationResult: ...


class DeterministicAnonymizer:
    """Interim driver: high-precision deterministic PII only (email, IBAN, BSN)."""

    def anonymize(self, text: str) -> AnonymizationResult:
        counts: dict[str, int] = {}
        text, counts["email"] = detectors.redact_email(text)
        text, counts["iban"] = detectors.redact_iban(text)
        text, counts["bsn"] = detectors.redact_bsn(text)
        return AnonymizationResult(text=text, counts=counts)
