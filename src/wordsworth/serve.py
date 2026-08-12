"""Production ASGI composition root.

``create_app()`` with no args serves only ``/health`` — each route is registered
per injected dependency. This wires the real backends from config so
``uvicorn wordsworth.serve:app`` serves the full read surface (document state,
metrics, search, hybrid, ask).

Backends are lazy (constructed here, connected on first request), so importing
this module performs no network I/O — the pod starts even when a backend is
briefly unavailable, and individual requests fail-hard per the invariants. The
API needs no object-store or anonymizer (ingestion does, not serving).

Schema creation (``init_schema``) is a separate one-shot step
(``wordsworth-init``), deliberately not run here: serving must not require DDL
privileges on every start.
"""
from __future__ import annotations

from fastapi import FastAPI

from .api import create_app
from .db import make_engine, make_session_factory
from .embedder import OllamaEmbedder
from .generator import OllamaGenerator
from .opensearch_index import OpenSearchIndex


def build_app() -> FastAPI:
    """Wire ``create_app`` to the real backends resolved from config."""
    engine = make_engine()
    return create_app(
        session_factory=make_session_factory(engine),
        search_index=OpenSearchIndex.from_config(),
        embedder=OllamaEmbedder.from_config(),
        generator=OllamaGenerator.from_config(),
    )


app = build_app()
