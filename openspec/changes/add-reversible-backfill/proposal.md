## Why

Reversible pseudonymisation applies from the moment it is enabled — but a corpus
already indexed with the irreversible anonymizer stays irreversible (bare `[BSN]`
placeholders, no mapping). To make an existing corpus revealable, those documents
must be re-run through the current reversible driver. This needs to be a
documented, repeatable, fail-safe capability, not a throwaway script.

## What Changes

- `pipeline.reanonymize(session, document_id, store, anonymizer, search_index,
  embedder)`: re-derives the source text from the object store by the document's
  key, runs the INJECTED (reversible) anonymizer, embeds, and index-upserts the
  new de-identified text, then overwrites the stored `DocumentText`. **Fail-safe
  ordering** — the new text is computed/embedded/indexed BEFORE the stored text is
  overwritten, so a failure leaves the existing entry and index untouched and
  propagates (never blanks a document, never leaves clear PII). Idempotent (stable
  keyed pseudonyms + upsert-by-id). Appends a `reanonymize` audit access event
  (from==to state, counts only) so the hash-chain stays valid. No-op for documents
  not in INDEXED/ANONYMIZED.
- `POST /reprocess` — mounts only in reversible mode (a session-scoped anonymizer
  factory present). Body `{document_ids?}`; default = all INDEXED documents.
  Continue-on-failure with per-document outcome counts
  `{reanonymized, skipped, retryable, failed}` (transient vs permanent, reusing
  the resilience classification).
- CLI `wordsworth reprocess [--all | --ids a,b]` posts to `/reprocess`.
- Operator runbook `docs/runbooks/reversible-backfill.md`.

## Capabilities

### Modified Capabilities
- `document-lifecycle`: a processed document can be re-de-identified in place
  through the current driver — fail-safe, idempotent, audited, index stays
  pseudonyms-only.

## Impact

- Code: `pipeline.py` (`reanonymize`), `api.py` (`/reprocess` + models, gated on
  the reversible anonymizer factory), `client.py` (`reprocess` + `_post_json`). No
  schema change; no new dependency; pipeline default and existing routes unchanged.
- Tests: DB-integration (backfill from irreversible → reversible; idempotency;
  fail-safe leaves entry intact; skip non-indexed; audit + chain verify) + local
  (route mounts only in reversible mode; CLI posts to `/reprocess`).
