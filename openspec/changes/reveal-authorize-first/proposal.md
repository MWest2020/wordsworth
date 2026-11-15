# reveal-authorize-first

## Why

`POST /documents/{id}/reveal` and `POST /documents/{id}/reveal.pdf` answer
about the document before the grant has decided anything (issue #487, found by
the security review of #485). On origin/main `b54c774`, `api.py` 1387-1399
(`reveal`) and 1522-1542 (`reveal.pdf`) run, in this order:

1. (`reveal.pdf` only) state `deleted` → 410 `document deleted`, for any grant
   id, even one that does not exist (`tests/test_delete_renders.py:96-99`
   asserts exactly that);
2. grant not found → 404 `unknown grant`;
3. no state for the id → 404 `unknown document`;
4. the document is superseded → 409 `document is superseded by <survivor id>;
   reveal on that one`;
5. only then `grants.authorize()` (recipient, status, expiry, scope, domain) →
   403 `grant not applicable`.

So anyone with a key and any grant id, not their own, can tell which document
ids exist (404 against 403), which are deleted (410), and read the id of the
live copy a superseded one points to. Since #485 a caller who is no reader is
refused on every corpus-read route before any lookup; the two reveal routes are
the last existence oracle for that caller. `share-recipient-read` (#439) and
`console-share` (#440) are exactly what hands non-readers a grant id, so their
deploy waits on this (`api-corpus-read-gate` task 6.4 already says so).

Decision: issue #487 (`waiting-on-mark`), default "authorize first, answer
every refusal the same way", accepted under Mark's standing "defaults ok" of
2026-11-14. This proposal is written on that default.

## What changes

- Both reveal routes judge the grant first: `grants.authorize()` on recipient,
  revocation, expiry and document scope runs before the API reads anything
  about the document (state, row, supersession, domain, box map, text).
- Every refusal to a caller the grant does not cover is one answer: 403
  `{"detail": "grant not applicable"}`. That covers an unknown grant, a
  revoked, expired or foreign grant, an unknown document, a superseded one, a
  deleted one, and a real live document outside the grant's scope.
- Only a caller the grant covers learns that the document is deleted (410, now
  on both routes) or superseded (409 naming the survivor, as before).
- A refusal writes no audit record and no log line that names its cause, the
  document's state or a survivor id.
- The two routes call one gate, so they cannot drift apart again.

Status codes that change, for a caller the grant does not cover:

| case | before | after |
|---|---|---|
| unknown grant id | 404 `unknown grant` | 403 `grant not applicable` |
| unknown document | 404 `unknown document` | 403 `grant not applicable` |
| superseded document | 409 naming the survivor | 403 `grant not applicable` |
| deleted document (`reveal.pdf`) | 410 `document deleted` | 403 `grant not applicable` |

For a caller the grant covers: superseded stays 409 naming the survivor;
deleted becomes 410 on `/reveal` too (it fell through to the text lookup
before). A recipient whose document-scoped grant was removed by the deletion
is no longer covered and gets the 403.

## What does not change

- What a covered caller can reveal, the types, the VC gate, the audit record
  of a successful reveal, `by_legal_basis`.
- 401 for a missing or wrong key and 422 for a malformed id or body still come
  first: they say nothing about the corpus.
- The grants spec: `authorize()` stays a pure decision and is not modified.
- The read routes (`GET /documents/{id}`, `/state`, `/redacted.pdf`, ...): a
  reader still sees `superseded`, 404 and 410 there, behind corpus read.
- The grant admin routes: `GET /grants/{id}` and `POST /grants/{id}/revoke`
  keep their 404 for an unknown grant; they are behind the reader or issuer
  gate.

## Capabilities

- `reveal-api`: the error-semantics requirement is rewritten; three
  requirements are added (grant before lookup, one refusal, no trace of the
  cause).
- `document-lifecycle`: "A copy is retired, not removed" names the survivor on
  reveal only to a caller the grant covers.

## Depends on / blocks

- Builds on #485 (`api-corpus-read-gate`), merged.
- Blocks the deploy of #439 and #440 (their task lists and
  `api-corpus-read-gate` task 6.4 already name #487).
