# SPDX-License-Identifier: MIT
"""Truth tables for the declarable gates (api-corpus-read-gate)."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import Depends, FastAPI, HTTPException

from wordsworth.read_gate import corpus_read, gate_of, grant_admin, grant_read


def _req(caller: str | None):
    return SimpleNamespace(state=SimpleNamespace(caller=caller))


def _allows(gate, caller: str | None) -> bool:
    try:
        gate(_req(caller))
    except HTTPException as exc:
        assert exc.status_code == 403
        return False
    return True


class TestCorpusRead:
    def test_on_the_list(self):
        assert _allows(corpus_read(["lezer"]), "lezer")

    def test_off_the_list(self):
        assert not _allows(corpus_read(["lezer"]), "derde")

    def test_no_caller_with_the_list_set(self):
        assert not _allows(corpus_read(["lezer"]), None)

    def test_empty_list_admits_everyone(self):
        assert _allows(corpus_read([]), "derde")
        assert _allows(corpus_read([]), None)


class TestGrantRead:
    def test_reader_who_is_no_issuer(self):
        gate = grant_read(["lezer"], ["uitgever"], auth_enabled=True)
        assert _allows(gate, "lezer")

    def test_issuer_who_is_no_reader(self):
        gate = grant_read(["lezer"], ["uitgever"], auth_enabled=True)
        assert _allows(gate, "uitgever")

    def test_neither(self):
        gate = grant_read(["lezer"], ["uitgever"], auth_enabled=True)
        assert not _allows(gate, "derde")

    def test_empty_read_list_admits_any_authenticated_caller(self):
        gate = grant_read([], ["uitgever"], auth_enabled=True)
        assert _allows(gate, "derde")


class TestGrantAdmin:
    def test_issuer(self):
        assert _allows(grant_admin(["uitgever"], auth_enabled=True), "uitgever")

    def test_not_an_issuer(self):
        assert not _allows(grant_admin(["uitgever"], auth_enabled=True), "lezer")

    def test_empty_issuer_list_admits_nobody(self):
        assert not _allows(grant_admin([], auth_enabled=True), "mark")

    def test_auth_disabled_admits_everyone(self):
        assert _allows(grant_admin([], auth_enabled=False), None)


class TestGateOf:
    def test_route_with_a_gate(self):
        app = FastAPI()
        gate = corpus_read(["lezer"])

        @app.get("/gated", dependencies=[Depends(gate)])
        def gated() -> dict:
            return {}

        route = next(r for r in app.routes if getattr(r, "path", None) == "/gated")
        assert gate_of(route) == "corpus-read"

    def test_route_without_a_gate(self):
        app = FastAPI()

        @app.get("/open")
        def open_route() -> dict:
            return {}

        route = next(r for r in app.routes if getattr(r, "path", None) == "/open")
        assert gate_of(route) is None
