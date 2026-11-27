# key-service-delete

## Why

ADR-0009, build B, fourth of four (the split of `key-service-vault`, see
`key-service-pseudonymise`). Deleting a document has to reach everything the
service holds for it: its data keys (crypto-shredding, ADR-0008), its
registry rows, every encrypted value no other document needs, and every grant
scoped to it, leaving only a tombstone. This change carries the two deletions,
the service's key-lifecycle chain, and the race that #465 fixed in wordsworth.

## What changes

- `DELETE /v1/originals/{document_id}`: destroy the document's data keys and
  evict them from the unwrap cache.
- `DELETE /v1/documents/{document_id}`: keys, registry rows, every mapping no
  other document is registered for, every grant scoped to the document; a
  tombstone keeps id and domain.
- The key-lifecycle chain's writer (`lifecycle.py`, advisory lock 4783), and
  the skeleton's `AccessAudit` docstring corrected from 4772 to 4783.
- Both deletions write a key-lifecycle event and an `access_audit` record in
  one transaction, in the order 4783 then 4782.
- Docs: both endpoints in `docs/reference/key-service-api.md`.

## Open questions

- **Which key rows a deletion destroys.** In wordsworth a key follows its
  object, not its document: `deletion_keys.doomed` keeps a key that another
  live document still claims (a superseded copy, a re-ingest, an
  OCR-recovered scan). The service has no documents table and cannot make
  that decision. Either the service destroys every key row it sealed for the
  document (as the spec has said since `key-service-vault`), or the calling
  service names the object keys whose last claim the deletion ends and the
  service destroys only those. Default: the first, as the spec says. `seal`
  never re-points a row to another document (`key-service-originals`), so a
  row's `document_id` is the document the service sealed it for; how
  wordsworth's shared objects reach the service is settled in
  `key-service-cutover` before any traffic, and this change's endpoints may
  change shape there. Asked as wordsworth `waiting-on-mark` issue (see the PR
  that split `key-service-vault`).

## Out of scope

The claim decision for objects shared between documents
(`key-service-cutover`, see the open question), wordsworth calling these
routes (`key-service-cutover`), reveal's 403 for a former grant recipient
(`key-service-reveal`, which relies on the scoped grants being deleted here).

## Depends on

`key-service-originals` (the document-key store and the open route, through
which "deleted means unopenable" is proved) and `key-service-pseudonymise`
(the registry, the known-documents table, the mapping store, the audit writer).
