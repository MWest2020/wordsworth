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

## Sealing the existing corpus (`originals-encrypt-existing`)

`originals-ingest-switch` only covers documents ingested from then on. The
corpus that existed before it (about 420 objects on the homelab) was still
plaintext. `wordsworth-seal-originals` seals those, one object at a time,
without ever losing a document:

```bash
wordsworth-seal-originals --dry-run          # lists what it would seal, changes nothing
wordsworth-seal-originals                    # seals every candidate, one object at a time
wordsworth-seal-originals --ids <uuid> ...   # only these documents (still live)
wordsworth-seal-originals --verify           # read-only: any live legacy original left?
```

Always run `--dry-run` first and read the report before dropping the flag.
The report's `before`/`after`
sections carry object counts, sealed/legacy counts and total bytes --
separately for `originals` and `scans` -- and `results` lists, per document, a
status and an object key (a content hash, never a filename or any text).

For each legacy original: mint its data key and commit that row before
writing anything, seal the plaintext under a temporary key, verify it opens
to the SHA-256 named in the object key, only then overwrite the real object,
verify again, then drop the temporary copy. **A failed verify leaves the
plaintext exactly where it was** and the document reported `failed` -- nothing
is lost, and nothing is silently retried as something else. Investigate a
`failed` document by hand (read the temporary `sealing/<sha256>` object if it
is still there, check the `document_keys` row, check the key service) before
re-running; re-running is safe either way, since every step resumes from
whatever the row and the store hold.

The original scan of a live document recovered by OCR (named in its
recovering `ocr` audit record) is sealed the same way and counted under
`scans` rather than the plain object count -- it is still a legacy plaintext
original, just not the document's current one.

### `gone`: a scan that is no longer in the store

A recovered document's scan can have been cleaned up already (an orphan
sweep, a manual removal) without that being this command's business: a scan
missing from the store, or one that raises on read between being listed and
being sealed, is reported with the status `gone`, counted as **neither**
sealed nor failed, and never turns the run's exit status non-zero. There was
nothing to seal, so there is nothing to investigate.

### Checking the migration finished

`--verify` re-lists every live document's original and every live recovered
document's scan and reports whether any of them is still legacy plaintext,
without changing anything:

```json
{"ok": true, "legacy": [], "gone": []}
```

`"ok": false` means `"legacy"` names at least one object key still to seal --
run `wordsworth-seal-originals` again. Run it repeatedly and on a schedule if
useful: a fully sealed corpus reports `sealed: 0, failed: 0` every time.
