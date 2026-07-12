# Habitat security — add-observability

_run_id security-add-observability-20260712-182548 · verdict ok · 2026-07-12T18:28:09Z_

---

All checks complete. Here is my verdict.

---

## SECURITY VERDICT — change `add-observability`: **PASS** ✅

Judged against `CLAUDE.md` + the change only. Read-only; deterministic scans shown above.

### 1. Secrets scan — PASS
- No keys, tokens, private keys, `.env`, or hardcoded credentials in the diff (`git diff main...HEAD`) or in the new-commit history (`git log -p main..HEAD`).
- No secret-handling code introduced. `structured_log.py` logs only `document_id`, `step`, `from`/`to` state, `duration_ms`, `level` — no payload/PII in log lines. `metrics.py` exposes only aggregate counts and stage timings.

### 2. Forbidden dependencies — PASS
- **No dependency changes at all** — `pyproject.toml` / `uv.lock` untouched.
- No `anonypy`, `MinIO`, CyberArk/Conjur, `PyMuPDF`/`fitz`, or AGPL introduced.
- `/metrics` emits Prometheus **text** directly (no client library), and structured logging uses stdlib `logging` + `json` — no new deps, consistent with the design's "no client dependency" claim. Sovereign: no external telemetry/APM contacted.

### 3. Audit hash-chain integrity — PASS
- Chain-building logic (`audit.py`, `hashing.py`, `models.py`) is **untouched**. `pipeline.transition()` still calls `audit.append()` with identical arguments; the record shape and hash computation are unchanged.
- New code is **read-only** over `audit_records`: `_last_ts` (SELECT), `metrics.py` and `report.py` (SELECT/aggregate only). No `UPDATE`/`DELETE`/`ALTER` on audit — append-only invariant preserved.
- `documents.current_state` remains **derived** (`DISTINCT ON (document_id) ... ORDER BY seq DESC`), never a stored mutable column — matches the state-machine invariant.
- The `.habitat/audit.jsonl` governance chain entry **verifies**: recomputed `entry_hash` = stored `7333b121…92aba7`, and `prev_hash=""` is the correct genesis (first entry). No gaps, no rewrites.
- Caveat (honest disclosure): the DB-backed `tests/test_audit.py` (incl. `test_verify_detects_tamper`) **could not be executed here** — no Docker/Postgres in this environment. This is not hand-waved: since the change makes zero modifications to chain construction or record shape, chain verification behaviour is unaffected by the diff. If Mark wants the executed-test evidence, it must run in a Postgres-enabled environment.

### Informational note (not a FAIL criterion)
The builder metadata records `diff_hash = e3b0c442…852b855`, which is the **sha256 of the empty string**. This is Habitat governance metadata (process-owned), not a `CLAUDE.md` security invariant, so it does not affect this verdict — but Mark may want to check why the builder recorded an empty-diff hash for a non-empty change.

**Protected files** (`CLAUDE.md`, `.claude/agents/`, `.github/`, `CODEOWNERS`): none touched.

No changes made — this role is read-only and issues a verdict only.
