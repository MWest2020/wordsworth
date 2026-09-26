"""The API composition root wires the full read surface — offline.

``create_app()`` with no deps serves only ``/health``; ``serve.build_app`` must
wire the real backends so state/metrics/search/hybrid/ask are all served.
Building the app opens no connections, so this runs without any backend.
"""
from __future__ import annotations

from wordsworth.serve import build_app


def _paths(app) -> set[str]:
    return {route.path for route in app.routes}


def test_build_app_exposes_full_route_set():
    paths = _paths(build_app())
    assert "/health" in paths
    assert "/documents/{document_id}/state" in paths  # session_factory wired
    assert "/metrics" in paths
    assert "/search" in paths                          # search_index wired
    assert "/hybrid" in paths                           # + embedder
    assert "/ask" in paths                              # + generator


def test_module_level_app_is_built():
    from wordsworth import serve

    assert "/ask" in _paths(serve.app)  # import-time build succeeded, no I/O


def test_production_rate_limits_are_shared_by_every_replica():
    """hoge-beschikbaarheid step 2: with two replicas, per-process buckets give
    every client two buckets. The composition root must wire the Postgres ones."""
    from wordsworth.rate_limit import RateLimitMiddleware
    from wordsworth.rate_limit_pg import PostgresTokenBucket

    mw = [m for m in build_app().user_middleware if m.cls is RateLimitMiddleware]
    assert len(mw) == 1
    limiters = mw[0].kwargs["limiters"]
    assert "/console/login" in limiters
    assert all(isinstance(b, PostgresTokenBucket) for b in limiters.values())


def test_production_prints_the_pipeline_log_once():
    """Transitions log at INFO. Without a handler they were written and never
    printed; with two they would print twice."""
    import io
    import logging
    import uuid

    from wordsworth.structured_log import log_transition

    build_app()
    build_app()                                     # idempotent: still one handler
    logger = logging.getLogger("wordsworth.pipeline")
    assert len(logger.handlers) == 1 and logger.level == logging.INFO
    # (Root has no handlers in production -- checked in the image -- so this
    # handler is the only printer. pytest adds its own to root, so that half is
    # verified live after deploy, not here.)
    handler, buf = logger.handlers[0], io.StringIO()
    old = handler.setStream(buf)
    try:
        doc = str(uuid.uuid4())
        log_transition(document_id=doc, from_state="registered", to_state="extractable",
                       step="profile", duration_ms=1.0)
    finally:
        handler.setStream(old)
    assert buf.getvalue().count(doc) == 1
