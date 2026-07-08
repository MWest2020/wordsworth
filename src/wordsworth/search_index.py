"""The search seam (driver/protocol pattern) and an in-memory test double.

The pipeline depends on the `SearchIndex` protocol, never on OpenSearch directly,
so the backend is swappable and tests need no live cluster."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Hit:
    document_id: str
    score: float
    object_key: str | None = None


@runtime_checkable
class SearchIndex(Protocol):
    def ensure_ready(self) -> None: ...
    def index(self, document_id: str, text: str, object_key: str) -> None: ...
    def search(self, query: str, size: int = 10) -> list[Hit]: ...


def _terms(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


@dataclass
class InMemoryIndex:
    """Term-overlap scorer — enough to prove wiring and ranking order in tests."""

    _docs: dict[str, tuple[str, str]] = field(default_factory=dict)

    def ensure_ready(self) -> None:
        pass

    def index(self, document_id: str, text: str, object_key: str) -> None:
        self._docs[document_id] = (text, object_key)  # idempotent upsert by id

    def search(self, query: str, size: int = 10) -> list[Hit]:
        q = set(_terms(query))
        hits = []
        for doc_id, (text, object_key) in self._docs.items():
            tokens = _terms(text)
            score = float(sum(1 for t in tokens if t in q))
            if score > 0:
                hits.append(Hit(doc_id, score, object_key))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:size]
