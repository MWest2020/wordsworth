"""Embedding seam. Local inference only (Ollama/bge-m3). A failed embedding is a
HARD error (EmbeddingError) — never a silent null-vector fallback (nulvector-gap).

The `DeterministicEmbedder` is a hashing embedder for tests: no model, no network,
reproducible, and semantically-ish (shared tokens -> shared dimensions) so kNN and
cosine behave meaningfully without a real model."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from typing import Protocol, runtime_checkable

from zeef.similarity import tokenize

from .config import settings


def _stable_bucket(token: str, dim: int) -> int:
    return int.from_bytes(hashlib.md5(token.encode()).digest()[:4], "big") % dim


class EmbeddingError(Exception):
    """Raised when an embedding cannot be produced. Never return a null vector."""


@runtime_checkable
class Embedder(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    """Local Ollama embeddings (bge-m3 default). No cloud in the critical path."""

    def __init__(self, url: str, model: str, dim: int):
        self.url = url.rstrip("/")
        self.model = model
        self.dim = dim

    @classmethod
    def from_config(cls) -> "OllamaEmbedder":
        return cls(settings.ollama_url, settings.embedding_model, settings.embedding_dim)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            payload = json.dumps({"model": self.model, "prompt": text}).encode()
            req = urllib.request.Request(
                f"{self.url}/api/embeddings", data=payload,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    body = json.loads(resp.read())
            except Exception as exc:  # network/timeout/HTTP -> hard error
                raise EmbeddingError(f"ollama embed failed: {exc}") from exc
            vector = body.get("embedding")
            if not vector or not any(vector):
                raise EmbeddingError("ollama returned an empty/null embedding")
            vectors.append([float(x) for x in vector])
        return vectors


class DeterministicEmbedder:
    """Hashing embedder for tests. Reproducible, non-null, no model or network."""

    def __init__(self, dim: int = 64):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in tokenize(text):
                vec[_stable_bucket(token, self.dim)] += 1.0
            if not any(vec):
                raise EmbeddingError("no tokens to embed (would be a null vector)")
            vectors.append(vec)
        return vectors
