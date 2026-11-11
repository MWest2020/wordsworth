---
status: draft
last_reviewed: 2026-11-11
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
