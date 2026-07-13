"""Answer-generation seam. Local inference only (Ollama). The LLM *advises*: it
phrases an answer over sources retrieval already chose, and cites their ids —
the deterministic guard in `rag.py` decides which citations survive.

A failed generation is a HARD error (GenerationError) — never a silent cloud
fallback (the no-silent-fallback / no-cloud invariants)."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .config import settings


@dataclass
class Source:
    document_id: str
    text: str  # de-identified passage handed to the model


@dataclass
class Answer:
    text: str
    citations: list[str] = field(default_factory=list)  # verified in rag.py


class GenerationError(Exception):
    """Raised when an answer cannot be produced. Never fall back to a remote API."""


@runtime_checkable
class Generator(Protocol):
    def generate(self, query: str, sources: list[Source]) -> Answer: ...


def _prompt(query: str, sources: list[Source]) -> str:
    blocks = "\n\n".join(f"[{s.document_id}]\n{s.text}" for s in sources)
    return (
        "Beantwoord de vraag UITSLUITEND op basis van de bronnen hieronder. "
        "Elke bron begint met haar id tussen blokhaken. Verzin niets; citeer de "
        "id van elke bron die je gebruikt. Als de bronnen geen antwoord geven, "
        "laat 'citations' leeg. Antwoord met JSON: "
        '{"answer": "<tekst>", "citations": ["<id>", ...]}.\n\n'
        f"BRONNEN:\n{blocks}\n\nVRAAG: {query}"
    )


class OllamaGenerator:
    """Local Ollama generation. No cloud in the critical path."""

    def __init__(self, url: str, model: str):
        self.url = url.rstrip("/")
        self.model = model

    @classmethod
    def from_config(cls) -> "OllamaGenerator":
        return cls(settings.ollama_url, settings.llm_model)

    def generate(self, query: str, sources: list[Source]) -> Answer:
        payload = json.dumps({
            "model": self.model,
            "prompt": _prompt(query, sources),
            "stream": False,
            "format": "json",
        }).encode()
        req = urllib.request.Request(
            f"{self.url}/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read())
            parsed = json.loads(body["response"])
        except Exception as exc:  # network/timeout/HTTP/bad-JSON -> hard error
            raise GenerationError(f"ollama generate failed: {exc}") from exc
        citations = parsed.get("citations") or []
        return Answer(
            text=str(parsed.get("answer", "")),
            citations=[str(c) for c in citations],
        )


class DeterministicGenerator:
    """Test double: echoes a fixed answer citing every given source id. No model,
    no network — proves the flow and the grounding guard without an LLM.

    `extra_citations` lets a test inject ids that are NOT among the sources, so the
    guard's drop-invented-citation behaviour is exercisable."""

    def __init__(self, extra_citations: list[str] | None = None):
        self.extra_citations = extra_citations or []

    def generate(self, query: str, sources: list[Source]) -> Answer:
        cited = [s.document_id for s in sources] + self.extra_citations
        return Answer(text=f"Antwoord op: {query}", citations=cited)
