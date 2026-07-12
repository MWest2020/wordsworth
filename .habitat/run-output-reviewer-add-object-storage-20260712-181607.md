# Habitat reviewer — add-object-storage

_run_id reviewer-add-object-storage-20260712-181607 · verdict ok · 2026-07-12T18:18:55Z_

---

I have everything needed for a verdict.

---

## Reviewer verdict: **PASS**

Change `add-object-storage` @ `96a382c` (impl `97706bf`), reviewed against `CLAUDE.md` + the change only.

### Checks

**1. Scope** ✅ — The diff implements exactly the change's specs/tasks:
- `object_store.py`: `ObjectStore` Protocol (put/get/exists) + `S3ObjectStore` (boto3) + `InMemoryObjectStore` double.
- `config.py`: S3 endpoint/bucket/region/creds via env.
- `pipeline.py`: new `ingest()` (put → content-addressed key → register), `process()` now fetches bytes by key instead of receiving `pdf_bytes`.
- Test edits across `test_pipeline`, `test_e2e`, `test_indexing_pipeline`, `test_anonymization_pipeline`, `test_pseudonymizer` are pure `process(store=…)`/`ingest()` signature migrations — no behavior beyond the new seam. The Habitat run commit adds only audit/report artifacts.

**2. No clear PII toward index** ✅ — Flow unchanged: anonymization still precedes indexing; `index.index(...)` receives `anonymized` text. The object store carries raw *source* bytes only; `object_key` is a storage key, not PII.

**3. No mutable audit tables** ✅ — No audit schema change; `current_state` remains derived from the latest record. Append-only chain untouched.

**4. No cloud APIs in critical path** ✅ — This is the self-hosted S3 seam (SeaweedFS PoC / Ceph RGW target) with a configurable endpoint; not a cloud API. Embeddings remain local (Ollama, unchanged).

**5. CLAUDE.md invariants** ✅
- `uv` used, not pip; `boto3>=…` added via `pyproject.toml` + `uv.lock`.
- Files ≤ 200 lines: object_store 94, config 68, pipeline 194.
- License: new deps are boto3/botocore/jmespath/s3transfer — all Apache-2.0, EUPL-1.2-compatible, no AGPL infection.
- No banned deps (grep for minio/anonypy/conjur/pymupdf: none).
- Driver/protocol pattern honored (Protocol + S3 driver + in-memory double).
- No silent fallbacks: missing key → `ObjectStoreError`; absent creds → hard error (no anonymous fallback); the null-vector rule in `process` is untouched.
- Secrets read from env injected by SOPS+age/OpenBao, never hardcoded (verified by `test_s3_from_config_*`).

**6. Done = green** ✅ (with an environment caveat) — The change's DB-free tests pass: 6/6 in `test_object_store.py`, including the invariant-critical sovereign-credential tests. The 2 pipeline-integration tests and the SeaweedFS integration test that didn't run failed/skipped **only** because `docker` (Postgres testcontainer) and a live SeaweedFS are absent in this sandbox — the same `FileNotFoundError: 'docker'` hits every DB-backed test repo-wide, including pre-existing `test_audit`/`test_mapping_store` unrelated to this change. This is an environment limitation, not a defect introduced by the change; the tests themselves are correctly written.

**Hard-fail check** ✅ — No diff touches `CLAUDE.md`, `.claude/agents/`, or CI config.

### Note for the merge owner (Mark)
The change is sound in isolation, but before "green" is truly asserted the DB-backed suite (`process`/`ingest` integration + SeaweedFS round-trip) must be run in an environment with docker/Postgres and a SeaweedFS endpoint available — that coverage could not be exercised here.
