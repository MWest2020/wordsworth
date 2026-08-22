## 1. reanonymize

- [x] 1.1 `pipeline.reanonymize` re-derives text from the store, runs the injected
  anonymizer, re-embeds + index-upserts, then overwrites `DocumentText`.
- [x] 1.2 Fail-safe ordering: overwrite stored text only after a successful
  re-index; a failure leaves the prior entry + index untouched and propagates.
- [x] 1.3 `reanonymize` audit event (from==to, counts only); no-op for non-
  INDEXED/ANONYMIZED; idempotent.

## 2. Batch + surfaces

- [x] 2.1 `POST /reprocess` (mounts only with a reversible anonymizer factory);
  default all INDEXED; continue-on-failure with outcome counts.
- [x] 2.2 CLI `wordsworth reprocess [--all | --ids …]` + `_post_json`.
- [x] 2.3 Operator runbook `docs/runbooks/reversible-backfill.md`.

## 3. Gate

- [x] 3.1 Local: route mounts only in reversible mode; CLI posts to /reprocess.
- [ ] 3.2 DB-integration (CI): backfill irreversible→reversible, idempotency,
  fail-safe leaves entry intact, skip non-indexed, audit + chain verify.
- [ ] 3.3 Full suite green in CI + `openspec validate`.
