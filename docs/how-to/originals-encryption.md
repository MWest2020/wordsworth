---
status: draft
last_reviewed: 2026-11-15
---

# Runbook: originals encryption

`originals-ingest-switch` wires `OriginalsStore` (ADR-0008) into the running
service: the API's `POST /ingest` and both batch CLIs (`wordsworth-ingest`,
`wordsworth-ingest --manifest`) now seal every new original under its own
data key before it reaches the object store, in both pseudonymisation modes.
See [the architecture reference](../reference/architecture.md#storage) for the
format and the `document_keys` table.

## Ingest order and rollback

`pipeline.ingest` registers the document first, then calls `write_original`
(`originals-ingest-write`): the row exists in the session before the object is
sealed and written, so a failure after the write rolls back only the object
this call wrote -- never a legacy object a live document still reads. Every
reader of an original -- `pipeline.process`, `pipeline.reanonymize`, OCR
recovery's input read, and the redacted/reveal PDF routes -- opens it through
`read_original` (`originals-ingest-readers`), which refuses to hand back
ciphertext as if it were a plain PDF.

## The key service down: the batch stops, by design

Sealing an original needs OpenBao Transit: minting a data key for a new
object, or unwrapping one to read an original back. There is no plaintext
fallback -- an empty `openbao_token` or an unreachable OpenBao gives `503` on
**every** ingest, by design, not a silent downgrade to an unsealed write.

The API's `POST /ingest` stops the batch at the first file that hits the
refusal and answers:

```json
{"detail": "key service unavailable",
 "total": <files in the request>,
 "indexed": <count of "indexed" among results>,
 "results": [<the IngestResult of every file completed before the failing one>]}
```

(the exact body `api.py` returns; see
[`docs/reference/ingest.md`](../reference/ingest.md#the-key-service-is-unreachable-the-batch-stops)
for what is and is not stored around it.) `wordsworth-ingest` and its
`--manifest` form fail the same way: non-zero exit, `key service unavailable`
on stderr, no further files attempted.

**Rollback**, if a deploy makes this worse rather than better: redeploy the
previous wordsworth image digest in homelab. There is no in-place toggle back
to plaintext ingest -- the previous image is the rollback.

## OCR recovery is sealed too

OCR recovery (`recovery.recover`) checks, before writing anything, whether
another live document already owns the key the OCR'd bytes would get; if so,
nothing is written and the scan's document is superseded by that owner
(`originals-ocr-sealed`). Otherwise the OCR'd PDF is written through
`write_original` like any other original: sealed, under its own
content-addressed key, with a `document_keys` row for the recovered document.
The scan object it was read from keeps its own key and row unchanged. If the
repoint of `object_key` or the state transition fails after a fresh write, the
written object is deleted so a retry starts clean.

## Sealing the existing corpus

`originals-ingest-switch` only covers new originals. The ~420 objects already
on the homelab, ingested before that change, stay legacy plaintext until
`wordsworth-seal-originals` (ADR-0008, `originals-encrypt-existing`) runs
against them:

```bash
wordsworth-seal-originals --dry-run          # reports what would be sealed; changes nothing
wordsworth-seal-originals                    # a real run: seals everything it finds
wordsworth-seal-originals --ids <uuid> <uuid> # a real run, limited to named documents
wordsworth-seal-originals --verify           # checks only: fails if a live document or its
                                              # scan is still legacy plaintext, or a sealed
                                              # object has no usable key row
```

A run without flags seals for real; `--dry-run` is the flag to pass first.
The dry run reports counts (`objects`, `sealed`, `legacy`, `missing`,
`unreadable`, `bytes`), the keys it would seal (`would_seal`) and the keys it
could not read (`unreadable`), and changes nothing.

**The dry run is cheap.** Classifying an object -- the dry run, the `before`
and `after` counts of a real run, and `--verify` -- costs one HEAD (the size)
and one ranged GET of the first 30 bytes (the sealed header: magic, version,
key id), never a download of the object. Only a real seal reads an object in
full, once, and retries that read once on a transient error (a broken stream,
a timeout) before reporting it failed. (Before this, a dry run downloaded
every object several times: on production, ~420 objects, it took over ten
minutes, and one broken 13 MB GET ended it with a traceback.)

**`missing` versus `unreadable`.** `missing` means the store answered that the
object does not exist. `unreadable` means the store did not answer usably --
a 5xx, a timeout, a connection broken mid-read: the object may well exist,
and may still be plaintext, so it is never counted as missing. No read error
ends a dry run or a `--verify`; every one is reported as `unreadable`. In a
real run an original that stays unreadable after the retry is reported
`"failed"` with the error `"unreadable"` (a missing one: `"missing"`), its
plaintext untouched, and the run goes on; a scan that cannot be read is
`"gone"`, as the spec says. Rerun once the store is healthy. A real run seals
every legacy original it finds for a live document, and the original scan
(`old_object_key` in its recovering `ocr` audit record,
`deletion_scans.scan_keys`) of every document that is not deleted --
superseded copies included -- when that scan is itself still plaintext; these
are counted separately in the report, under `scans`.

**Never without a readable copy.** Per object: the sealed bytes are written
first under a temporary key (`sealing/<sha256>`) and verified to open to the
object's recorded SHA-256 *before* the plaintext at `documents/<sha256>` is
ever overwritten. A sealed copy that fails that check leaves the plaintext in
place and the document reported `"failed"`, never `"sealed"`. After the
overwrite the final key is verified again; if it does not open (a corrupted
write, a read error), the verified temporary copy is put back at the final
key and verified once more, and the temporary copy is deleted only once the
final key verifies. If it still does not, the object is reported `"failed"`
and `sealing/<sha256>` is kept: by then it is the readable copy. `put_original`
is deliberately not used for this: it refuses to replace a legacy object,
which is right for ingest and wrong for this migration.

**One object never ends the run.** Any exception while sealing one object
(the key service unavailable, a store error) is reported as `"failed"` with
the exception's class name only (e.g. `OriginalsKeyUnavailable`), never its
message, and the run moves on to the next object.

**Beside a deletion.** The seal runs alongside the service, so a document can
be deleted while the run is underway. Each object is sealed in two
transactions (read and mint the key row; then write, verify and set
`sealed_at`), each holding the document's row `FOR SHARE` and re-checking
first that the document is not deleted and still claims the object. A
deletion that starts during either waits for it to commit and then removes
what it wrote, key row included; a deletion that committed before either is
found by the re-check: the object is reported `"skipped_deleted"` (counted
under `skipped_deleted`, not as failed), nothing is written at
`documents/<sha256>`, and a temporary copy no other document claims is
removed. A claim that moved without a deletion (OCR recovery repointed the
document while the run was underway) is reported `"skipped_moved"` and left
for the next run, which finds the object as the document's scan. The run
never takes the audit chain's lock.

**Idempotent and resumable.** A document already sealed (`sealed_at` set) is
reported `"already_sealed"` and its object is not touched (a leftover
temporary copy is removed). The original scan of a live recovered document
that the store no longer has (it does not exist, or reading it raises an
object-store error) is reported with the status `"gone"` and counted under
`gone`: neither sealed nor failed, and the exit status stays clean. A run interrupted between the overwrite and the `sealed_at` commit
leaves a sealed object with no `sealed_at` yet; a rerun finds exactly that
state, verifies it -- restoring it from `sealing/<sha256>` if it does not
open -- and finishes the commit; it never re-reads a plaintext that is
already gone. A run interrupted after the key row was minted and before
anything was written reuses that row. Safe to run repeatedly, including on a
schedule, until `--verify` reports `"verified": true`.

**What `--verify` checks.** It fails (exit 1) while a live document's
original or a scan is still legacy plaintext, or while a sealed object can
be opened by no one: it has no key row (`no_key_row`) or its header names
another key id than its row (`key_id_mismatch`), or while a live document's
original is missing from the store (`missing`: data loss, never a pass), or
while a live document's original cannot be read (`unreadable`: it may still
be plaintext, so that fails too -- the safe side). It also lists, without
failing on them, pending objects -- sealed, `sealed_at` still NULL
(`pending`), which a rerun finishes -- and scans it could not read
(`unreadable`, `"kind": "scan"`). **Run one seal at a time:** two runs at
once share the temporary `sealing/<sha>` copies. Object keys and ids only, never content; it needs no key service.

**On a failed document.** The report names the object key and an error, never
document content. Investigate the object directly (is it reachable, does the
key service answer) and rerun -- a prior failure does not block any other
document, and rerunning retries only what is still legacy or still pending.

## Deploy precondition

Merging `originals-ingest-switch` does not deploy it. Wordsworth images reach
the cluster through a digest bump in homelab. Before that bump, both of these
must exist, with the evidence in the homelab PR -- they are deploy
preconditions in *that* PR, not build tasks in this change:

- a restore-tested backup of the `document_keys` table;
- an off-node OpenBao snapshot that holds the originals KEK.

Without them, a lost key row or KEK makes a sealed original unreadable for
good. Default if that evidence isn't there: the image is not rolled out, and
new documents stay plaintext until it is.
