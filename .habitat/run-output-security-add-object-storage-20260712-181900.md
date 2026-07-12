# Habitat security — add-object-storage

_run_id security-add-object-storage-20260712-181900 · verdict ok · 2026-07-12T18:23:17Z_

---

All three checks complete. Here is my verdict.

---

## Security verdict: **PASS** — `add-object-storage`

Judged against `CLAUDE.md` + this change only. I'm read-only; no files modified.

### 1. Secrets scan — ✅ PASS
- No hardcoded keys/tokens/private-keys/credentials in the diff (`git diff main...HEAD`) or branch history (`git log -p main..HEAD`).
- No `.env`/`.pem`/`.key`/`.age` files added.
- S3 creds resolve **only** via `os.environ` (`WORDSWORTH_S3_ACCESS_KEY`/`_SECRET_KEY`), documented as SOPS+age/OpenBao-injected — never hardcoded, client-side, or commercial (`config.py:53-63`, `object_store.py:35-49`).
- `S3ObjectStore.from_config` raises `ObjectStoreError` on missing creds — no silent anonymous fallback, honoring the "no silent fallbacks" invariant.

### 2. Forbidden dependencies — ✅ PASS
- No `MinIO`, `anonypy`, `CyberArk`/`Conjur`, or `PyMuPDF` in `pyproject.toml` or `uv.lock`.
- Only new dep is **`boto3>=1.43.44`** (Apache-2.0 → EUPL-1.2 compatible). Backend stays behind the S3 seam (SeaweedFS PoC / Ceph RGW target), a config change not a code change — matches the change intent and the MinIO ban rationale.

### 3. Audit hash-chain integrity — ✅ PASS
- `audit.py`, `hashing.py`, `models.py` are **UNCHANGED** by this diff — chain semantics (`hash = sha256(prev_hash ‖ canonical_content)`, `seq`/hash fields excluded) are intact.
- Pure hash-chain unit tests green: `tests/test_hashing.py` **4 passed** (determinism, key-order stability, tz-aware enforcement, prev+content dependency).
- Pipeline still emits an audit `transition` per step; `ingest` merely stores bytes then calls the unchanged `register`. Fetch-by-key is a lazy read that raises `ObjectStoreError` on a missing key (hard error, no empty-bytes fallback) — consistent with the null-vector rule.

### Scope & governance
- Change touches only `config.py`, `object_store.py`, `pipeline.py`, tests, `pyproject.toml`/`uv.lock`, and its own OpenSpec files. Does **not** modify `CLAUDE.md`, `.claude/agents/`, or CI — governance boundary respected.

### Note (not a FAIL)
The DB-backed tests (`test_audit.py`, `test_pipeline.py`) and the SeaweedFS integration test error/skip here because **docker is unavailable in this sandbox**, not due to the change — these are environmental. All three security checks are independently runnable and were shown clean/green above. If Mark wants full-suite green, run the audit/pipeline tests in an environment with docker + a reachable SeaweedFS.
