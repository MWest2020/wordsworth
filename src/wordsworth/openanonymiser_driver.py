"""OpenAnonymiser-backed driver behind the ``Anonymizer`` seam.

Composite: the deterministic detectors run FIRST (audited structured-PII
precision — BSN elfproef, IBAN mod-97, email), then OpenAnonymiser (Presidio +
spaCy NER, local CPU) redacts entity PII such as personal names. Counts are
merged per type into one ``AnonymizationResult``.

Invariants: inference is local (no cloud); replacement is irreversible (typed
placeholders, no mapping); an engine failure raises ``AnonymizationEngineError``
— un-redacted text is never passed through (no silent fallbacks).
"""
from __future__ import annotations

import os
from typing import Callable, Protocol

from .anonymizer import AnonymizationResult, DeterministicAnonymizer


class AnonymizationEngineError(RuntimeError):
    """The anonymization engine failed. Deliberately carries no document text."""


class _EngineFn(Protocol):
    def __call__(self, text: str) -> tuple[str, dict[str, int]]: ...


def _configure_cpu_plugins() -> None:
    """Point OpenAnonymiser at its packaged CPU config (``plugins.classic.yaml``:
    spaCy NER + patterns) unless the operator already set ``PLUGINS_CONFIG``.
    The upstream default ``plugins.yaml`` enables GLiNER, which needs the
    torch/CUDA ``gpu`` extra — not installed, and not the PoC path."""
    if "PLUGINS_CONFIG" in os.environ:
        return
    from importlib import resources

    classic = resources.files("src.api").joinpath("plugins.classic.yaml")
    if not classic.is_file():
        raise AnonymizationEngineError(
            "OpenAnonymiser is installed without plugins.classic.yaml"
        )
    os.environ["PLUGINS_CONFIG"] = str(classic)


def _openanonymiser_redact(text: str) -> tuple[str, dict[str, int]]:
    """Analyze + anonymize via OpenAnonymiser; return (redacted text, counts).

    Engines are module-level singletons upstream, so the slow spaCy model load
    happens once per process, on first call."""
    _configure_cpu_plugins()
    from src.api.services import text_analyzer

    results = text_analyzer.analyze(text)
    engine_result = text_analyzer.anonymize(text, results)
    counts: dict[str, int] = {}
    for item in engine_result.items:  # what was actually replaced
        label = item.entity_type.lower()
        counts[label] = counts.get(label, 0) + 1
    return engine_result.text, counts


class OpenAnonymiserAnonymizer:
    """``Anonymizer`` driver delegating to OpenAnonymiser, composed with the
    deterministic detectors. Construction is cheap; models load on first use."""

    def __init__(self, engine: _EngineFn | None = None) -> None:
        # ``engine`` is a test seam only; the default is the real local engine.
        self._engine = engine or _openanonymiser_redact
        self._deterministic = DeterministicAnonymizer()

    def anonymize(self, text: str) -> AnonymizationResult:
        deterministic = self._deterministic.anonymize(text)
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
