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
