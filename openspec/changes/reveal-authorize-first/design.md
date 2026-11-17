# Design: reveal-authorize-first

Closes #487. Code references are to origin/main `b54c774`.

## Words

- **The uniform refusal**: status 403, body `{"detail": "grant not
  applicable"}`, content type `application/json`. A browser that asks for
  HTML gets the console's 403 page (`api.py` `forbidden`), which shows the
  path and the caller's own label and nothing about the cause; that page is
  the same for every cause too. The string is today's 403 detail, so clients
  that already handle the 403 keep working.
- **Covered**: a request is covered when `grants.authorize()` returns a
  non-empty set for that grant and that document, with the document's own
  domain. That includes the recipient check (auth on), status, expiry, scope,
  the global-grant gate (flag or global role) and the domain.
- **A grant covers no document that does not exist.** An unknown id has no
  domain to bind to and nothing to reveal; it is refused for every caller,
  including the holder of a global grant.

## The order

One function decides for both routes. Proposed: new module
`src/wordsworth/reveal_gate.py` (under 200 lines; `api.py` is 2002 lines and
`grants.py` 359, neither should grow):

```python
REFUSAL = HTTPException(status_code=403, detail="grant not applicable")

def decide(session, grant_store, grant_id, document_id, *, caller,
           auth_enabled, allow_global, now, pdf: bool) -> Decision:
    # 1. the grant, judged without reading the document
    grant = grant_store.get(grant_id)              # None -> REFUSAL
    permitted = permitted_types(grant, resolve_role)
    if not authorize(grant, document_id, permitted, now,
                     grant.domain or DEFAULT_DOMAIN,   # domain-blind pass
                     allow_global, caller, auth_enabled, ...):
        raise REFUSAL
    # 2. only now: the document. Both reads always run (or one query),
    #    so an unknown id costs what a document in another domain costs.
    state = current_state(session, document_id)
    dom = document_domain(session, document_id)
    if state is None:
        raise REFUSAL                              # no grant covers it
    allowed = authorize(grant, document_id, permitted, now, dom, ...)
    if not allowed:
        raise REFUSAL                              # other domain
    # 2b. the VC gate (pure, no reads), as part of "covered"
    vc_types, vc_audit = apply_vc_gate(allowed, x_vc, ...)  # VcError -> 403
    # 3. covered: the answers about the document
    if state == State.DELETED:      raise 410 "document deleted"
    if copy.superseded_by:          raise 409 "... superseded by <id> ..."
    if pdf and no box map:          raise 409 "no box map yet ..."
    if no anonymized text:          raise 409 "document not yet de-identified"
    return Decision(grant, permitted, dom, ...)
```

Step 1 is `grants.authorize()` itself, not a copy of its checks: called with
the grant's own domain, the domain comparison holds trivially and every other
check (status, recipient, expiry, scope, global gate, role resolution) runs as
it always does. Role resolution reads the `roles` table, which says nothing
about any document. Step 2 is the real decision, with the document's domain.

**The clever pitfall.** The two `authorize()` calls look redundant, and
somebody will "simplify" them into one. Dropping the second loses the domain
binding; dropping the first brings the oracle back. Both are pinned by tests
(the domain test in `tests/test_domain_keys.py:85` and the new no-lookup
test), and the function's docstring says why there are two.

Why not change `authorize()` (for example `domain=None` meaning "skip"): a
`None` that skips a check is fail-open, and the grants spec promises a pure
decision with fixed meaning. A new parameter there would be a second promise
to keep; the domain-blind call needs none.

**The domain is decided before 410 and 409, for every grant.** For a scoped
grant the scope already pins the document; for an unscoped one (flag on, or
a `beheerder` role grant) the domain is the only thing between a holder in
domain A and the deletion or supersession of a document in domain B. A test
pins the order (task 2.2).

**The VC gate moves into "covered".** Today it runs after the 409 superseded
check, so with `vc_required` a grant holder without a valid credential still
hears 409 naming the survivor (and on `reveal.pdf` 410). `apply_vc_gate` is
pure and reads nothing, so it moves to step 2b at no cost: a caller it
rejects gets 403 `vc rejected: ...` as today, before any answer about the
document. `decide` returns the VC's narrowing and audit fields; the route
intersects the requested types with them as it does now, and verifies the
credential once.

The routes keep everything after the gate as it is: types requested, the
second `authorize()` for the requested types, `deanonymize`, the audit
record, the response.

## What "before any document lookup" means here

Not read before step 1 passes: `current_state`, `session.get(Document, ...)`,
`document_domain`, `BoxMap`, `get_anonymized_text`, the pseudonym registry,
the object store. Read: the grant store and, for a role grant, the `roles`
table. The test for this listens on the engine (`before_cursor_execute`) and
fails if a statement naming `documents`, `audit_records`, `document_texts`,
`document_pseudonyms`, `pii_mappings`, `box_maps`, `document_summaries` or
`dossier_documents` runs during a refused request (the table names in
`models.py` at `b54c774`).

## Deleted documents

Today `reveal.pdf` checks `deleted` before the grant, because the deletion
removes the document's own grants and a grant lookup would answer 404 for
the grant the caller still holds (#451). That is the oracle in its plainest
form: 410 for any grant id, `no-such-grant` included, so it goes.

After this change:

- a document-scoped grant is gone after the deletion (in `PostgresGrantStore`,
  the production store; `InMemoryGrantStore` keeps it, so tests of this use
  the Postgres store), so its former recipient
  gets the uniform refusal. He held a grant on that one document, so he
  learns nothing he did not know, and the refusal is honest: the grant no
  longer exists.
- a grant that survives the deletion and covers the document (a global grant
  where the deployment allows it, or a `beheerder`/admin role grant) gets
  410, on both routes. On `/reveal` that is new: it used to fall through to
  "not yet de-identified" (409), which was wrong for a deleted document.
- `GET /documents/{id}/redacted.pdf` keeps its 410: it is behind corpus read
  since #485, and a reader may know.

`tests/test_delete_renders.py:96-99` asserts the old behaviour and is
rewritten (task 3.3).

## Refusals leave no trace of their cause

Today a refusal writes no audit record (the document chain only records what
happened to a document; a refusal on an unknown id could not even reference
one) and the routes log nothing. This change keeps both and makes them a
promise:

- no record on the document audit chain, none in the key-lifecycle stream;
- no application log line, metric label or error detail that names the
  cause, the document's state, or a survivor id. The response layer sees one
  `HTTPException`, so FastAPI, the 403 handler and the access log (method,
  path, status) see the same thing for every cause.

An operator who needs to know why a reveal was refused asks the routes that
have their own gate: `GET /grants/{id}` (reader or issuer) for the grant,
`GET /documents/{id}/state` (reader) for the document. Writing the cause to a
log for convenience would make the log a copy of the oracle, readable by
whoever reads logs; the shares make that a wider circle than today.

## Residual: timing

A caller refused in step 1 triggers no document read, so his refusals take
the same path whatever the document. A caller who passes step 1 holds either
a grant scoped to that very id (he knows it existed at issue) or a global
grant (he may reveal any document of his domain). Step 2 reads state and domain
for an unknown id as for a document in another domain, so those two make the
same queries; what remains is noise in the database and in Python. No
constant-time promise is made; this is named so nobody mistakes the
identical bodies for one.

## Found and not changed

- `docs/how-to/console.md:33` uses "an unknown grant" as an example of a 404
  a route answers. That stays true for `GET /grants/{id}`; the docs task only
  checks the sentence does not point at the reveal routes.
- `api.py` stays over its 200-line limit; this change moves code out of it,
  not in.
