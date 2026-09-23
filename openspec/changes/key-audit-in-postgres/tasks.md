# Tasks: key-audit-in-postgres

The order matters: the table first, then the writers, then proof.

## 1. The table
- [x] 1.1 `KeyLifecycleEvent` model: `seq` (bigserial PK), `ts`, `action`,
      `actor`, `payload` (JSONB), `prev_hash` (UNIQUE), `hash` (UNIQUE).
- [x] 1.2 Append-only trigger on it, created by `wordsworth-init` next to the
      one on `audit_records`. Test: an UPDATE and a DELETE both raise.
- [x] 1.3 Chaining: its own advisory-lock key and genesis; `append` and
      `verify_chain` following the pattern in `audit.py`. Test: tampering with
      one row is detected at that row's `seq`.

## 2. The driver
- [x] 2.1 `PostgresKeyLifecycleAudit` implementing the existing
      `KeyLifecycleAudit` protocol — every method the JSONL driver has,
      including `dossier_renamed`.
- [x] 2.2 One factory for production entry points; `_resolve_audit()` returns
      the Postgres driver.
- [x] 2.3 The JSONL driver stays, as a test double only.

## 3. Every writer reaches it
- [x] 3.1 `wordsworth-dossier-hernoem` passes the stream. Test: a rename through
      the CLI entry point produces a `dossier_renamed` event.
- [x] 3.2 A production writer given no stream raises instead of returning.
      `dossier_events.renamed` and `roles._noteer` first.
- [x] 3.3 Walk every caller of `grant_issued`, `grant_revoked`,
      `role_changed`, `dossier_renamed` and `rotation`, and record in this file
      which ones reach the stream. Not assumed: listed.

      Walked 2026-09-23 (`grep` for each method name and for every caller of
      its wrapper). "Same session" means the event and the change commit in
      one transaction.

      | Event | Writer | Entry point | Reaches the table |
      |---|---|---|---|
      | `grant_issued` | `grants.issue_grant` | `POST /grants` | yes, same session (`PostgresGrantStore(session)` does not commit on its own) |
      | `grant_revoked` | `grants.revoke_grant` | `POST /grants/{id}/revoke` | yes, same session |
      | `role_changed` | `roles.create` / `set_types` / `deactivate` / `activate` via `_noteer` | API role routes | yes, same session (`_resolve_audit(session)`) |
      | `role_changed` | same | console role pages | yes, same session (`create_app` passes `_resolve_audit` to the console) |
      | `role_changed` | `roles.create` | `wordsworth-init` bootstrap of the admin role | yes, same session. **Before this change: none** |
      | `dossier_renamed` | `dossier_events.renamed` via `dossiers.rename` | `wordsworth-dossier-hernoem` | yes, same session. **Before this change: none** — no rename was ever recorded |
      | `rotation` | `key_lifecycle.rotate_keys` | none — no production caller, tests only | n/a until something rotates keys; the caller will have to pass a stream, the signature requires one |

      A writer given `None` now raises `MissingAuditStream` (`renamed`,
      `_noteer`); `issue_grant`, `revoke_grant` and `rotate_keys` take the
      stream as a required positional argument.

## 4. The export
- [x] 4.1 `key_audit_export` reads the table and serialises in `seq` order, the
      way `audit_export.export_jsonl` does for the document chain.
      It verifies the chain before exporting and the stored bytes after
      (`key_audit_pg.verify_jsonl`, which needs no database). `seq` has gaps
      after a rollback, so counts come from the rows. Still no scheduled caller
      — that was true before this change too, and is not this change's scope.

## 5. Proof
- [ ] 5.1 Restart test, in the cluster, not in pytest: issue a grant, restart
      the api pod, the event is still there and `verify_chain` holds.
- [ ] 5.2 Write down what was lost before this change landed, with the date of
      the last restart that erased it.
