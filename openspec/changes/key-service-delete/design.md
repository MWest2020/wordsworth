# Design

Both routes sit behind the skeleton's service token (401 first). This
change's tests run under the fixture that makes `config.settings` raise,
against FakeTransit and the service's own test database.

## The key-lifecycle chain

`lifecycle.py` holds `append_lifecycle(session, *, action, actor, payload)`
and `verify_lifecycle_chain(session)`: under `pg_advisory_xact_lock(4783)`,
over the service's `KeyLifecycleEvent` (copied from wordsworth's), with the
same content and hash construction as wordsworth's `key_audit_pg` (the same
canonical content of `ts`, `action`, `actor`, `payload`;
`hashing.compute_hash`; `GENESIS_HASH`), so a verifier that reads one reads
the other. It cannot be `key_audit_pg.append`, which queries wordsworth's
model (skeleton rule 3). The actor is the service caller.

The skeleton's `AccessAudit` docstring says the service's key-lifecycle lock
is 4772; that is wordsworth's key in another database, and the order written
in `key-service-pseudonymise` fixes 4783. The docstring is corrected here, by
the first writer of that chain.

## Locks

Both deletions take, in one transaction, the order of
`key-service-pseudonymise`: lock 1 (4781, `DELETE /v1/documents` only), the
`known_documents` row, the `document_keys` rows `FOR UPDATE` by `object_key`,
the `pii_mappings` rows `FOR UPDATE` by token, then 4783 for the lifecycle
event, then 4782 for the audit record, last.

Decided: one transaction for the lifecycle event and the audit record, key
lifecycle first. Rejected: audit before key lifecycle (the audit would stop
being the terminal lock, and every later lifecycle writer would have to reason
about it); two transactions (a destroyed key with no audit record if the
second fails). Because it is one transaction, the counts in a response are
those of a committed deletion; a failure commits nothing and reports nothing.
The two records are never separable; this sentence is here so that a later
writer does not split them.

## `DELETE /v1/originals/{document_id}`

Destroys every `document_keys` row whose `document_id` is the document and
evicts those object keys from this process's unwrap cache (`doc_keys.evict`;
correctness on other replicas comes from `unwrap` checking the row on every
call). 200 `{"destroyed": n}`; idempotent (n = 0 the second time). One
lifecycle event (`action = "keys_destroyed"`, the document, the key ids) and
one `access_audit` record (`event = "delete_originals"`, the count). After it,
`open` for that document answers 404 (`key-service-originals`).

Which rows: see the open question in `proposal.md`. Under the default, the
rows the service sealed for this document, which is well defined because
`seal` refuses an object key that belongs to another document instead of
re-pointing it. wordsworth's shared objects (a superseded copy or a re-ingest
sharing an object key, an OCR-recovered document claiming its scan) are not
represented in the service; `key-service-cutover` decides how wordsworth's
claim decision reaches the service before anything calls this route.

## `DELETE /v1/documents/{document_id}`

Under lock 1: destroy the document's keys (as above), delete its
`document_tokens` rows, delete every `pii_mappings` row whose token no other
document is registered for, delete every grant scoped to the document
(`grants.document_id` = the id, as `deletion.py` does in wordsworth today),
and set `known_documents.deleted_at` (the row keeps id and domain; no value,
no token). 200 `{"keys": n, "tokens": n, "mappings": n, "grants": n}`.

- **Already tombstoned:** the same call again. `keys`, `tokens` and
  `mappings` are 0 (nothing is left), `grants` counts any scoped grant
  created since and deleted now (normally 0). The tombstone is unchanged.
- **Never seen** (no `known_documents` row): `keys`, `tokens` and `mappings`
  are 0, scoped grants are deleted all the same and counted in `grants` (a
  grant may name a document the service has not seen), and no tombstone is
  written: `known_documents.domain` is NOT NULL and the service does not know
  the domain. A later `pseudonymise` of that id registers it fresh. Rejected:
  404 (a deletion must never be blockable, and wordsworth may delete a
  document that was never pseudonymised); a tombstone with a placeholder
  domain (a made-up value in the column reveal judges grants against).

One lifecycle event (`action = "document_deleted"`, the document, the
destroyed key ids, the deleted grant ids) and one `access_audit` record
(`event = "delete_document"`, the counts).

Deleting the scoped grants keeps a promise of reveal-api: the former recipient
of a grant on a deleted document gets the uniform 403, not 410. Only a grant
that survives the deletion (unscoped where allowed, or under a global role)
covers a deleted document and hears 410.

## The #465 twin

A deletion decides "no other document holds this token" under lock 1, and a
`pseudonymise` of the same value for another document stores the mapping
under lock 1 too, so either the deletion sees the new registry row or the
mapping is stored again after it. Two connections prove it, whichever commits
first.

## Residual

ADR-0009 already records that the service credential alone can crypto-shred
any document; nothing here changes that row.

## Modules

`api_documents.py` (both deletions), `lifecycle.py`. Each ≤ 200 lines.
