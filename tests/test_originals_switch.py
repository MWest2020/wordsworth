# SPDX-License-Identifier: MIT
"""`originals-ingest-switch` (step 4 of 4): `serve.build_app` passes one
process-lifetime `OriginalsStore` as `store`, in both pseudonymisation modes,
and shares its `transit_for` with the reversible key provider -- ADR-0008 made
true for the running service. Offline: `S3ObjectStore.from_config` is stubbed
and OpenBao Transit never leaves the process, so no backend is contacted.

Proves task 1.1 via `app.state.store`/`app.state.transit_for` only -- the
surface the proposal names, no private attribute."""
from __future__ import annotations

from wordsworth.config import settings
from wordsworth.object_store import InMemoryObjectStore, S3ObjectStore
from wordsworth.originals_store import OriginalsStore


def _stub_s3(monkeypatch) -> None:
    monkeypatch.setenv("WORDSWORTH_S3_ACCESS_KEY", "test-access")
    monkeypatch.setenv("WORDSWORTH_S3_SECRET_KEY", "test-secret")
    monkeypatch.setattr(S3ObjectStore, "from_config",
                        classmethod(lambda cls: InMemoryObjectStore()))


def _set_openbao(monkeypatch) -> None:
    monkeypatch.setenv("WORDSWORTH_OPENBAO_URL", "http://openbao.test:8200")
    monkeypatch.setenv("WORDSWORTH_OPENBAO_TOKEN", "test-token")


def test_build_app_wires_an_originals_store_in_irreversible_mode(monkeypatch):
    monkeypatch.delenv("WORDSWORTH_REVERSIBLE", raising=False)
    _stub_s3(monkeypatch)
    _set_openbao(monkeypatch)
    from wordsworth.serve import build_app

    app = build_app()

    assert isinstance(app.state.store, OriginalsStore)
    assert callable(app.state.transit_for)


def test_build_app_wires_an_originals_store_in_reversible_mode(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_REVERSIBLE", "true")
    _stub_s3(monkeypatch)
    _set_openbao(monkeypatch)
    from wordsworth.serve import build_app

    app = build_app()

    assert isinstance(app.state.store, OriginalsStore)


def test_build_app_with_no_s3_creds_has_no_store(monkeypatch):
    monkeypatch.delenv("WORDSWORTH_REVERSIBLE", raising=False)
    monkeypatch.delenv("WORDSWORTH_S3_ACCESS_KEY", raising=False)
    monkeypatch.delenv("WORDSWORTH_S3_SECRET_KEY", raising=False)
    _set_openbao(monkeypatch)
    from wordsworth.serve import build_app

    assert build_app().state.store is None


def test_reversible_key_provider_shares_build_apps_transit_for(monkeypatch):
    """The reversible key provider's `DurableKeyProvider` is built from the
    SAME `transit_for` that `app.state.transit_for` exposes -- one unwrap
    cache per process (proposal.md). Proved without reaching into
    `app.state`'s private key-provider attribute: a spy on `OpenBaoTransit`
    shows exactly one instance minted for the KEK name the reversible wiring
    used, and asking `app.state.transit_for` for that same name afterwards
    mints no second one."""
    import wordsworth.transit as transit_mod

    monkeypatch.setenv("WORDSWORTH_REVERSIBLE", "true")
    _stub_s3(monkeypatch)
    _set_openbao(monkeypatch)

    created = []

    class _SpyTransit:
        def __init__(self, *args, **kwargs):
            created.append(self)

        def wrap(self, plaintext: bytes) -> bytes:
            raise AssertionError("not needed for this proof")

        def unwrap(self, ciphertext: bytes) -> bytes:
            raise AssertionError("not needed for this proof")

    monkeypatch.setattr(transit_mod, "OpenBaoTransit", _SpyTransit)
    from wordsworth.serve import build_app

    app = build_app()
    assert len(created) == 1  # the reversible key provider's own transit

    app.state.transit_for(settings.transit_kek_name)  # same KEK name, after build

    assert len(created) == 1  # still one: the shared closure served it from cache
