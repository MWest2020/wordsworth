# Habitat security — add-caching

_run_id security-add-caching-20260711-223201 · verdict ok · 2026-07-11T22:34:34Z_

---

All checks complete. Verdict below.

---

## Security verdict — `add-caching`: **PASS**

Judged against `CLAUDE.md` + the change only. Diff scope (`git diff main...HEAD`): `src/wordsworth/cache.py`, `tests/test_cache.py`, `openspec/changes/add-caching/tasks.md` (checkbox flips), and harness-generated artifacts (`.habitat/audit.jsonl`, `run-report.json`, HTML report).

**1. Secrets scan — PASS**
- Grep over the full diff and the branch's one new commit for keys/tokens/private-keys/`.env`/passwords/bearer/AWS-ID/`ghp_`/`xox…` patterns: no matches.
- `cache.py` imports stdlib only (`hashlib`, `collections`, `typing`) + internal `.embedder`. No credentials, no client-side/hardcoded secret path.

**2. Forbidden dependencies — PASS**
- No `anonypy`, `MinIO`, CyberArk/Conjur, or AGPL (`PyMuPDF`/`fitz`) in the diff.
- No dependency-manifest change (`pyproject.toml`/`uv.lock` untouched) — the in-memory `LruCache` adds no new dependency, consistent with the proposal ("no new dependency for the PoC").

**3. Audit hash-chain integrity — PASS**
- The pipeline append-only audit chain (`src/wordsworth/audit.py`, `hashing.py`, `models.py`) is **not touched** by the change — the `hash = sha256(prev_hash ‖ canonical(record))` invariant is preserved by construction. Nothing in the diff can write to, update, or delete audit records.
- The design explicitly composes with the invariants: a failed embedding raises before any `cache.set`, so failures are never cached (nulvector rule), and a cache miss recomputes the identical uncached result — caching affects latency only, never outputs. `test_failed_embedding_is_not_cached` and `test_caching_embedder_matches_uncached_output` pin this.

**Notes**
- `tests/test_cache.py`: **16 passed**. The 22 errors in the wider suite are `FileNotFoundError: 'docker'` (testcontainers Postgres/OpenSearch) and OpenSearch-unreachable skips — environmental, pre-existing, unrelated to this change; none touch `cache.py`.
- I could not independently reproduce the `entry_hash` in the harness-owned `.habitat/audit.jsonl` (no Habitat hashing spec exists in-repo, and its scheme differs from the pipeline's — genesis `prev_hash` is `""` vs. the pipeline's `GENESIS_HASH`). This is Habitat run-audit metadata, outside the wordsworth pipeline audit invariant my check governs; it is a single genesis entry with no gaps or rewrites to verify.

The change adds only the caching seam and its tests, modifies nothing owned by Mark (`CLAUDE.md`, `.claude/agents/`, CI), and holds all three security invariants.
