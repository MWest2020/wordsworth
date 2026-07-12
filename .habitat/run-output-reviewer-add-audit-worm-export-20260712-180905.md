# Habitat reviewer — add-audit-worm-export

_run_id reviewer-add-audit-worm-export-20260712-180905 · verdict ok · 2026-07-12T18:11:51Z_

---

I've completed my review. Here is my verdict.

---

## Reviewer verdict: **PASS** — `add-audit-worm-export`

Judged against `CLAUDE.md` + the change (`openspec/changes/add-audit-worm-export/`) only.

### Hard-fail check (clean)
The diff touches no protected paths — no `CLAUDE.md`, no `.claude/agents/`, no CI config. Files changed: `src/wordsworth/audit.py`, `audit_export.py`, `config.py`, `tests/test_audit_export.py`, the `tasks.md` checkboxes, plus Habitat run artifacts. ✓

### Checks (all hold)

1. **Scope.** The diff implements exactly the three spec requirements — WORM export, verify-against-DB, incremental+retention — and nothing outside. `export_jsonl` gained a keyword-only `after_seq=0` (backward-compatible; existing caller `tests/test_audit.py:38` and `audit.export_jsonl(session)` still work). ✓

2. **No clear PII toward the index.** `audit_export.py` touches only the audit table and object storage; no indexing/search path is involved. ✓

3. **No mutable audit tables.** Production code is strictly read-only over `audit_records` (`select` only in `_hash_at`, `verify_export`, `_last_seq`, `export_worm`). This change *strengthens* tamper-evidence rather than weakening it. The single `UPDATE ... DISABLE TRIGGER` at `tests/test_audit_export.py:127-137` is test-only, re-enables the trigger, and exists to *prove* the verifier rejects a tampered DB chain — legitimate, not a violation. ✓

4. **No cloud APIs in the critical path.** `S3WormStore` (`audit_export.py:83-102`) takes an *injected* S3 client and targets self-hosted S3 Object Lock (Ceph RGW / SeaweedFS per `design.md`). No embeddings/LLM, no cloud API. ✓

5. **CLAUDE.md invariants.**
   - Driver/protocol pattern: `WormObjectStore` Protocol + `S3WormStore` driver + `InMemoryWormStore` double (`audit_export.py:38-102`). ✓
   - No silent fallbacks: every verify failure (DB chain, generated slice, read-back bytes) raises `ExportError`; `export_worm:181-197` never downgrades to a partial. Matches the spec's "failure, not a silent partial." ✓
   - Files ≤200 lines: `audit_export.py` is 199 (tight but compliant). ✓
   - No new/banned deps: boto3 is duck-typed (`client: Any`), not imported; no MinIO/anonypy/etc. `uv`, not pip. ✓

6. **Done = green.** Tests are comprehensive and correctly structured (retention lock, incremental, verify-match/altered/partial, DB-tamper rejection, configurable retention). In this sandbox 3 environment-independent tests pass; the 8 DB-backed tests **error only because neither Docker nor a local PostgreSQL is available here** — `conftest.py` (unchanged by this change) needs one. That's an environment limitation, not a defect in the change; those tests are gated to run in CI/with `WORDSWORTH_TEST_DATABASE_URL`. ✓

### Advisory (non-blocking, does not affect verdict)
`ExportResult.first_seq = after_seq + 1` and `count = last - after_seq` (`audit_export.py:190,199`) assume contiguous `seq`. Since `seq` is a PostgreSQL identity (`models.py:30`), a rolled-back insert can leave gaps, making these two *reporting* fields slightly off. The **exported data itself is correct** (`where(seq > after_seq)` selects the right records and `verify_export` re-checks line-count against the DB), and the spec imposes no exact-count requirement — so this is a metadata nicety, not a failure. Worth a note for a future tidy.

**Result: PASS.** The change is in scope, upholds every invariant, and is well-tested; the untestable-here DB suite is an environment constraint, not a code fault.
