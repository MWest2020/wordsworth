# Habitat security — add-rate-limiting

_run_id security-add-rate-limiting-20260712-183449 · verdict ok · 2026-07-12T18:37:14Z_

---

All three security checks complete. Here is my verdict.

## Security verdict — change `add-rate-limiting`

**PASS** (read-only; no files modified).

### 1. Secrets scan — PASS
`git diff main..HEAD` scanned for keys/tokens/private-keys/credentials/`.env`/`.pem`/`.key`. Every match is a Python identifier or type name (`TokenBucket`, `api_key` local, `x-api-key` header lookup) or a test fixture (`X-API-Key: alice/bob`). No hardcoded secrets, no key/`.env` files added. Config is env-driven only (`config.py`), consistent with the SOPS+age/OpenBao rule.

### 2. Forbidden dependencies — PASS
The change adds **zero** dependencies — `git diff main..HEAD -- pyproject.toml uv.lock` is empty. `rate_limit.py` builds on `starlette`, already present transitively via FastAPI. No `anonypy`, `MinIO`, `CyberArk`/`Conjur`, and no `PyMuPDF`/AGPL anywhere in the manifests.

### 3. Audit hash-chain integrity — PASS (by construction)
The change touches **no** wordsworth audit source: `src/wordsworth/audit.py`, `hashing.py`, `models.py`, `db.py` are byte-identical to `main`. The append-only, hash-chained audit (sha256(prev_hash ‖ record)) is unaltered, so the chain still verifies end-to-end. `tests/test_rate_limit.py`: **10 passed**. The audit test suite (`test_audit.py`) could not execute in this sandbox — it needs `docker`/testcontainers for PostgreSQL (`FileNotFoundError: 'docker'`), an environment limit rather than a change regression, and the tamper-detection logic it covers lives in the unchanged audit module.

### Out-of-scope observations (for the reviewer / Mark — not security failures)
The branch diff carries changes beyond `add-rate-limiting` that are outside my three checks but worth flagging:
- Deletes `.mcp.json` and two unrelated proposals (`add-thesis-evaluation`, `apply-docs-contract`); edits `add-audit-worm-export/tasks.md` (checkbox text only, not audit source).
- Adds `.habitat/audit.jsonl` and `run-report.json` (Habitat run infra — a separate builder-run log, not the CLAUDE.md wordsworth audit chain).

These are scope/ownership concerns in the **reviewer's** domain, not mine. None touch secrets, forbidden deps, or the wordsworth audit chain, so they don't change my verdict. I made no modifications.
