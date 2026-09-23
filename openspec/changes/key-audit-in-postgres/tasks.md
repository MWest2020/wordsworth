# Tasks: key-audit-in-postgres

The order matters: the table first, then the writers, then proof.

## 1. The table
- [ ] 1.1 `KeyLifecycleEvent` model: `seq` (bigserial PK), `ts`, `action`,
      `actor`, `payload` (JSONB), `prev_hash` (UNIQUE), `hash` (UNIQUE).
- [ ] 1.2 Append-only trigger on it, created by `wordsworth-init` next to the
      one on `audit_records`. Test: an UPDATE and a DELETE both raise.
- [ ] 1.3 Chaining: its own advisory-lock key and genesis; `append` and
      `verify_chain` following the pattern in `audit.py`. Test: tampering with
      one row is detected at that row's `seq`.

## 2. The driver
- [ ] 2.1 `PostgresKeyLifecycleAudit` implementing the existing
      `KeyLifecycleAudit` protocol — every method the JSONL driver has,
      including `dossier_renamed`.
- [ ] 2.2 One factory for production entry points; `_resolve_audit()` returns
      the Postgres driver.
- [ ] 2.3 The JSONL driver stays, as a test double only.

## 3. Every writer reaches it
- [ ] 3.1 `wordsworth-dossier-hernoem` passes the stream. Test: a rename through
      the CLI entry point produces a `dossier_renamed` event.
- [ ] 3.2 A production writer given no stream raises instead of returning.
      `dossier_events.renamed` and `roles._noteer` first.
- [ ] 3.3 Walk every caller of `grant_issued`, `grant_revoked`,
      `role_changed`, `dossier_renamed` and `rotation`, and record in this file
      which ones reach the stream. Not assumed: listed.

## 4. The export
- [ ] 4.1 `key_audit_export` reads the table and serialises in `seq` order, the
      way `audit_export.export_jsonl` does for the document chain.

## 5. Proof
- [ ] 5.1 Restart test, in the cluster, not in pytest: issue a grant, restart
      the api pod, the event is still there and `verify_chain` holds.
- [ ] 5.2 Write down what was lost before this change landed, with the date of
      the last restart that erased it.
