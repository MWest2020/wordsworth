# Habitat security — add-audit-worm-export

_run_id security-add-audit-worm-export-20260712-181156 · verdict ok · 2026-07-12T18:16:02Z_

---

Verdict issued below. The repo is untouched — as the security agent I make no changes; I report.

---

## Security verdict: **PASS** — change `add-audit-worm-export`

Judged against `CLAUDE.md` + the change only. All three checks ran deterministically and hold.

### 1. Secrets scan — ✅ clean
- Diff (`cefce9e..HEAD`), branch history, and habitat artifacts (`run-report.json`, builder HTML, `.habitat/audit.jsonl`): no keys, tokens, private-key material, `.env`, or hardcoded credentials.
- Only secret-*like* hit is a docstring in `audit_export.py:13-14` documenting that S3 creds "come from object-storage's secret source, **never hardcoded**" — the `S3WormStore` client is injected, consistent with the SOPS+age / OpenBao invariant. No manifest (`pyproject.toml`/`uv.lock`) changes.

### 2. Forbidden dependencies — ✅ none
- No `anonypy`, `MinIO`, CyberArk/Conjur introduced; no AGPL/PyMuPDF (`fitz`) anywhere in the tree (excluding `.venv`). The change adds no new dependency — WORM is a boto3-style injected client behind a `Protocol` seam.

### 3. Audit hash-chain integrity — ✅ verified end-to-end
Docker/PostgreSQL were unavailable, so rather than declare the check unrunnable I exercised the change's **real** code paths (`audit.export_jsonl(after_seq=…)`, `verify_export`, `export_worm`, `InMemoryWormStore`) against a SQLite-backed session. Confirmed:
- `verify_chain` = True; full export re-verifies; `sha256(prev_hash ‖ canonical(record))` recomputes correctly and links (`prev_hash == prev.hash`) for every record — **no gaps, no rewrites**.
- **Tamper detection:** an altered exported field with a stale hash → rejected; a dropped line (partial) → rejected.
- **No silent partial:** a tampered *DB* chain raises `ExportError("database chain does not verify at seq 1")` — the export fails hard, per the invariant.
- **Incremental:** `after_seq` slices only records past the last exported `seq`; nothing-new writes no object.
- **WORM write-once:** the retention-lock guard (overwrite/delete blocked until `retain_until`, released only after expiry) passes via the repo's own pure-logic tests (`3 passed`).

The change is confined to a read-only derived view (`export_jsonl` gains an `after_seq` filter) plus the new export module — the append path, `hashing.py`, and `compute_hash` are untouched, so chain-writing integrity is preserved by construction.

No findings for Mark or the builder to act on.
