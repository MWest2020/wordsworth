# originals-encrypted-ingest-proofs

## Why

`originals-encrypted-ingest` was built once and failed: the builder ran out of
its budget (194 turns, $13.53) on wordsworth#345. The change is split. The
production switch (sealed write at ingest, the five readers, the transit
factory, the fixture churn) stays in `originals-encrypted-ingest`. This change
is the remainder: the proof-tests of encrypted ingest and the docs that
describe it. The ordering and failure behaviour below were decided in that
change (amended in PR #346, after the architect's open questions); nothing new
is decided here.

## What changes

- Proof-tests that ingest registers the document **before** it writes the
  original (the key row carries the document id).
- A proof-test that when ingest fails after a `PutResult.WROTE`, the written
  object is deleted again (rollback), and that a `put_original` that did not
  write (existing object) is never deleted.
- Proof-tests for fail closed: 503 `key service unavailable` from `POST /ingest`
  in reversible and irreversible mode with nothing in the store; a batch stops
  at the first `OriginalsKeyUnavailable`, files already committed stay stored
  and sealed, and the 503 body lists them.
- A proof-test that OCR recovery reads its input through `get_original`.
- A test that pins the known gap: OCR recovery still writes with the plain
  `put` until `originals-ocr-sealed`, and its legacy-plaintext result still
  reads.
- Any test still on the old `store` signatures after the ingest build is
  migrated here.
- Docs: `docs/how-to/originals-encryption.md`, `docs/reference/ingest.md`,
  `docs/reference/architecture.md`, `docs/reference/cli.md` (see tasks.md).

No production code changes beyond what these tests expose. If a test exposes a
defect, the fix is made in the smallest form and named in the PR.

## Depends on

`originals-encrypted-ingest` merged **and built** first. The tests exercise its
`OriginalsStore` wiring, `mem_originals` fixture and the shared transit helper;
none of them can run before it. Task 0 checks this and stops if it does not
hold.

The requirements for register-first, the batch stop with its per-file report,
and OCR recovery reading through the originals store live only in
`originals-encrypted-ingest`. This change adds one requirement of its own
(rollback deletes only what the call wrote) and tests the others without
restating them.

The partial builder branch
`habitat/builder/originals-encrypted-ingest-20261102-090002-12705` is the
starting point of `originals-encrypted-ingest`, not of this change.

## Open questions

- None decided here. Whether sealing gets a switch is still Mark's call on
  #318; if he decides so, a follow-up change adds it explicitly.

## Out of scope

The OCR write itself (`originals-ocr-sealed`), destroying keys on deletion
(`originals-crypto-shred`), the existing corpus (`originals-encrypt-existing`),
and every production change already in `originals-encrypted-ingest`.
