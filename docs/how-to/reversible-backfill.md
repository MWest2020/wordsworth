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

## Also backfills the redacted-PDF box map

Since `pdf-redaction`, `reanonymize` computes the box map (page, rect, token —
never a value) right after re-deriving the text, whenever a key provider and
mapping store are passed through — which `wordsworth reprocess`/`POST
/reprocess` now do automatically in reversible mode. Running this backfill
over the 12 pilot documents and `gooise-meren-woo-2022` therefore also builds
their box maps; a document the run could not locate a value for gets a
`value-not-located` audit record instead of a box map, and is reported in
`problems`, not hidden — naming the document, the PII type and the counts,
read `located of in-text` (e.g. `0 of 1 located` means the value occurs once
in the text and none of its occurrences could be located), never the value.
See [pdf-redaction](pdf-redaction.md).

## After the one-PDF-extraction change (pdf-redaction-locate)

`anonymize` and `reanonymize` now record `text_source` (`pdfium-v1` for a PDF
run through `positioned_text`). `{"only_outdated": true}` picks up every
document whose last de-identification record lacks `text_source` `pdfium-v1`
— in addition to the existing lists-hash check — so a corpus last processed
under the retired pypdf extraction is reprocessed without having to name it
explicitly. `reanonymize` also reports, per run, the count of pseudonyms this
document had registered before the run that its newly-derived text no longer
carries ("orphaned" — the new extraction can split or join a value
differently from the old one); counts only, by PII type, never a token or a
value.

## After a normalisation-profile change

Tokens are derived from `normalize(type, value)` (see `normalization.py`,
`PROFILE_VERSION`). When the rule set changes, the version is bumped and every
existing mapping row still carries the version it was derived under
(`pii_mappings.norm_version`; `NULL` = legacy raw derivation). Re-derive the
corpus with the same `POST /reprocess` run as above — the stored original values
are unchanged, only the tokens move onto the new profile. Never re-derive
implicitly.
