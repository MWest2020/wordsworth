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

        store = S3ObjectStore.from_config()

    # Reversible mode (ADR-0002): pseudonymise with durable keyed tokens and mount
    # the key-gated reveal route. Session-scoped backends (durable keys, Postgres
    # mapping/grant stores) are supplied as per-request factories, so no OpenBao
    # I/O happens at import — the pod boots even if OpenBao is briefly sealed.
    # Default (off) keeps the irreversible OpenAnonymiser driver and no reveal.
    reversible: dict = {}
    if settings.reversible_mode:
        reversible = _reversible_wiring()
    elif store is not None:
        from .openanonymiser_driver import OpenAnonymiserAnonymizer

        anonymizer = OpenAnonymiserAnonymizer()

    return create_app(
        session_factory=make_session_factory(engine),
        search_index=OpenSearchIndex.from_config(),
        embedder=OllamaEmbedder.from_config(),
        generator=OllamaGenerator.from_config(),
        store=store,
        anonymizer=anonymizer,
        **reversible,
    )


def _reversible_wiring() -> dict:
    """`create_app` kwargs for reversible mode: one shared OpenBao Transit client,
    and session-bound stores built fresh per request (so a fresh session backs
    each pipeline run and reveal). No OpenBao call happens here — only per
    request."""
    from .grants import PostgresGrantStore
    from .keys import DurableKeyProvider
    from .mapping_store import PostgresMappingStore
    from .pseudonymizer import ReversibleAnonymizer
    from .transit import OpenBaoTransit, PostgresKeyVaultStore

    transit = OpenBaoTransit(
        settings.openbao_url, settings.openbao_token, settings.transit_kek_name
    )

    def key_provider(session):
        return DurableKeyProvider(
            PostgresKeyVaultStore(session), transit, settings.key_cache_ttl
        )

    def anonymizer(session):
        return ReversibleAnonymizer(key_provider(session), PostgresMappingStore(session))

    return {
        "anonymizer_factory": anonymizer,
        "key_provider_factory": key_provider,
        "grant_store_factory": lambda session: PostgresGrantStore(session),
    }


app = build_app()
