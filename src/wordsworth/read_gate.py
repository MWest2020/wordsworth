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

from typing import Callable

from fastapi import HTTPException, Request

from .auth import authorize_corpus_read, authorize_grant_issue


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
