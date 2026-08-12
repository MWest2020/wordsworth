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
from .config import settings
from .db import make_engine, make_session_factory
from .embedder import OllamaEmbedder
from .generator import OllamaGenerator
from .opensearch_index import OpenSearchIndex


def build_app() -> FastAPI:
    """Wire ``create_app`` to the real backends resolved from config.

    The write path (``POST /ingest``) is wired only when S3 credentials are
    configured — it needs the object store + the OpenAnonymiser driver. Without
    creds the app serves the read surface only, so importing this module never
    requires secrets."""
    engine = make_engine()
    store = None
    anonymizer = None
    if settings.s3_access_key and settings.s3_secret_key:
        from .object_store import S3ObjectStore
        from .openanonymiser_driver import OpenAnonymiserAnonymizer

        store = S3ObjectStore.from_config()
        anonymizer = OpenAnonymiserAnonymizer()
    return create_app(
        session_factory=make_session_factory(engine),
        search_index=OpenSearchIndex.from_config(),
        embedder=OllamaEmbedder.from_config(),
        generator=OllamaGenerator.from_config(),
        store=store,
        anonymizer=anonymizer,
    )


app = build_app()
