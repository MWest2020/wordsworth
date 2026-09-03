---
status: draft
last_reviewed: 2026-09-03
---

# Runbook — reversible backfill

Re-process an already-indexed corpus through the **reversible** de-identify driver
so documents first indexed irreversibly (bare `[BSN]` placeholders, no mapping)
become key-gated-revealable (`[BSN:hash]` keyed tokens + encrypted mappings +
OpenBao-wrapped data keys).

## What it does

For each target document, `reanonymize`:
1. re-derives the source text from the object store by the document's content key
   (never from a clear-text store);
2. runs the current (reversible) anonymizer → new de-identified text;
3. re-embeds and **upserts** the new text into the search index;
4. only then overwrites the stored `DocumentText`;
5. appends a `reanonymize` audit event (counts only, no clear values).

## Invariants

- **Fail-safe:** steps 2–3 happen before step 4, so a failure leaves the existing
  stored text and index entry untouched — a document is never blanked and clear
  PII never reaches the index. A batch continues past a failing document.
- **Idempotent:** stable keyed pseudonyms + upsert-by-id → safe to re-run; a
  second pass yields the same text and one index entry.
- **Audited:** the hash-chain still verifies; the event carries no clear values.
- Only documents in `INDEXED`/`ANONYMIZED` are processed; others are skipped.

## Preconditions

- Reversible mode is live: `WORDSWORTH_REVERSIBLE=true`, OpenBao reachable and
  **unsealed**, the `wordsworth-openbao` token present. If OpenBao is sealed, the
  run fails safe (documents stay as-is, reported retryable) — unseal and re-run.

## How to run

CLI (all INDEXED documents, or a subset):
```sh
wordsworth reprocess --all
wordsworth reprocess --ids <uuid1>,<uuid2>
```

HTTP:
```sh
curl -X POST "$WORDSWORTH_API_URL/reprocess" \
  -H 'content-type: application/json' -d '{}'            # all INDEXED
curl -X POST "$WORDSWORTH_API_URL/reprocess" \
  -H 'content-type: application/json' -d '{"document_ids":["<uuid>"]}'
```

Response is a per-document tally: `{total, reanonymized, skipped, retryable,
failed}`.

## Notes

- **Long-running:** one GLiNER pass per document on CPU — a full corpus takes a
  while. It is safe to re-run; already-reversible documents re-derive to the same
  tokens. Retryable documents (e.g. a transient OpenAnonymiser/OpenBao blip) are
  simply picked up again on the next run.
- The pre-existing corpus's original bytes must still be in the object store
  (they are, unless orphan-cleaned); the backfill reads from there.
