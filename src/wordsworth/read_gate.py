# SPDX-License-Identifier: MIT
"""The corpus-read and grant-admin checks as declarable FastAPI dependencies
(api-corpus-read-gate).

A check called from a route's body only runs once the body runs: after
parameter validation and after whatever lookup the route does first. Moving it
into ``dependencies=[Depends(gate)]`` on the route decorator makes it run
before both, so a caller without the right gets the same 403 for an id that
exists and one that does not, and for a complete request and an incomplete
one. It also makes the check visible to a test without running the route:
``gate_of(route)`` reads the gate's name off ``route.dependant``, where a call
inside a function body cannot be seen without executing it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

from .auth import authorize_corpus_read, authorize_delete, authorize_grant_issue


class Gate:
    """A FastAPI dependency that raises 403, and names itself."""

    def __init__(self, name: str, detail: str,
                allowed: Callable[[str | None], bool]) -> None:
        self.name = name
        self._detail = detail
        self._allowed = allowed

    def __call__(self, request: Request) -> None:
        caller = getattr(request.state, "caller", None)
        if not self._allowed(caller):
            raise HTTPException(status_code=403, detail=self._detail)


def corpus_read(labels: list[str]) -> Gate:
    """Corpus read: a label on ``labels``, or any caller when it is empty."""
    return Gate("corpus-read", "caller not authorized for corpus read",
               lambda caller: authorize_corpus_read(caller, labels))


def grant_read(labels: list[str], issuer_labels: list[str],
              auth_enabled: bool) -> Gate:
    """``GET /grants/{id}``: a corpus reader or a grant issuer, not a grant's
    recipient as such — the two are the only callers with a reason to read a
    grant (see design.md)."""

    def allowed(caller: str | None) -> bool:
        return (authorize_corpus_read(caller, labels)
                or authorize_grant_issue(caller, issuer_labels, auth_enabled))

    return Gate("grant-read", "caller not authorized to read this grant", allowed)


def grant_admin(issuer_labels: list[str], auth_enabled: bool) -> Gate:
    """The grant-issue right, declared: the same decision
    ``authorize_grant_issue`` makes for issuing and revoking, now also for
    ``POST /datasets/pseudonymize`` (confirming a guessed value is resolving a
    token, which takes the same right as minting one)."""
    return Gate("grant-admin", "caller not authorized to issue or revoke grants",
               lambda caller: authorize_grant_issue(caller, issuer_labels, auth_enabled))


def gate_of(route) -> str | None:
    """The name of the gate ``route`` declares via ``dependencies=[Depends(...)]``,
    or ``None`` if it declares none. Reads ``route.dependant`` rather than
    calling the route, so a test can require a gate without a request."""
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return None
    for dependency in dependant.dependencies:
        call = getattr(dependency, "call", None)
        if isinstance(call, Gate):
            return call.name
    return None


class GateFirst(APIRoute):
    """A route whose declared gates run before FastAPI reads the request body.

    A declared gate already runs before validation, but FastAPI parses a form
    body before it resolves any dependency: for an upload, a caller without
    the right still had his files read and spooled to disk before the 403
    (ingest-requires-corpus-read). This route class runs the same `Gate`
    objects first, then the normal handler, which runs them once more."""

    def get_route_handler(self):
        handler = super().get_route_handler()
        gates = [d.call for d in self.dependant.dependencies
                 if isinstance(d.call, Gate)]
        if not gates:
            raise TypeError(f"GateFirst on {self.path} without a declared gate")

        async def gate_first(request: Request):
            for gate in gates:
                gate(request)
            return await handler(request)

        return gate_first


@dataclass(frozen=True)
class Gates:
    """Every caller check ``create_app`` hands its routes, built once from the
    resolved label lists, so no route can close over a list still ``None``."""

    auth_enabled: bool
    corpus_read: Gate
    grant_read: Gate
    grant_admin: Gate
    delete: Callable[[Request, object], None]


def build(*, keys, identity, corpus_read_labels: list[str] | None,
          grant_issuer_labels: list[str] | None, grants_configured: bool,
          settings) -> Gates:
    """Resolve the two label lists against ``settings`` and build the gates.

    ``auth_enabled`` follows exactly what the auth middleware mounts on
    (``keys or identity is not None``). S1: when the two drifted apart, an
    installation with only an identity provider was authenticated while the
    recipient binding was off -- every grant a bearer token again, and anyone
    could mint one. One source for "is there a caller to decide about".

    With authentication and a grant store on and the read list empty, this
    logs one warning: the scope is off and every authenticated caller reads
    the corpus. Legal, so not a refusal to start; but more likely forgotten
    than chosen where somebody is deciding who sees what."""
    readers = (settings.corpus_read_labels if corpus_read_labels is None
               else corpus_read_labels)
    issuers = (settings.grant_issuer_labels if grant_issuer_labels is None
               else grant_issuer_labels)
    auth_enabled = bool(keys) or identity is not None
    if auth_enabled and grants_configured and not readers:
        from .structured_log import log_empty_corpus_read_scope

        log_empty_corpus_read_scope()

    def delete(request: Request, session) -> None:
        """Deleting is irreversible: the admin role or a named issuer label
        only. The role is resolved here because ``authorize_delete`` touches
        no database."""
        from .grants import caller_holds_role
        from .roles import ADMIN

        caller = getattr(request.state, "caller", None)
        groups = getattr(request.state, "groups", ()) or ()
        beheerder = bool(caller or groups) and caller_holds_role(
            session, caller, ADMIN, groups=groups)
        if not authorize_delete(caller, issuers, auth_enabled,
                                is_beheerder=beheerder):
            raise HTTPException(status_code=403,
                                detail="caller not authorized to delete")

    return Gates(auth_enabled=auth_enabled, corpus_read=corpus_read(readers),
                 grant_read=grant_read(readers, issuers, auth_enabled),
                 grant_admin=grant_admin(issuers, auth_enabled), delete=delete)
