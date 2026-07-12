# Habitat reviewer — add-rate-limiting

_run_id reviewer-add-rate-limiting-20260712-183249 · verdict ok · 2026-07-12T18:34:45Z_

---

Confirmed: the 22 errors are `FileNotFoundError: 'docker'` — pre-existing environmental failures (docker/Postgres-dependent tests) present on `main` too, entirely unrelated to this change. The change's own tests pass 10/10.

I have everything needed for a verdict.

---

## Reviewer verdict: **PASS**

Change `add-rate-limiting` reviewed against `CLAUDE.md` + the change only.

### Hard-fail check
- No diff touches `CLAUDE.md`, `.claude/agents/`, or CI/CODEOWNERS. ✓

### Checks
1. **Scope** ✓ — Diff is exactly the change: `rate_limit.py` (token-bucket + `RateLimitStore` + in-memory store + middleware), `config.py` (per-endpoint rate/burst settings), `api.py` (middleware wiring, test-injectable), `test_rate_limit.py`. Remaining diff entries (`.habitat/audit.jsonl`, run-report/HTML, `tasks.md` checkboxes) are builder-run artifacts, not out-of-scope code. Maps cleanly onto tasks 1.1–2.2 and the spec's three requirements.
2. **No clear PII toward index** ✓ — Not applicable; client key is API-key/IP held as an in-memory bucket key, never sent to the index. `_hit` still omits raw vectors.
3. **No mutable audit tables** ✓ — No audit schema/state changes.
4. **No cloud APIs in critical path** ✓ — Pure in-memory token bucket; Redis is only mentioned as a future option behind the same interface, not implemented.
5. **CLAUDE.md invariants** ✓ — `uv` used (not pip); files ≤200 lines (155/78/65); **no new dependency** (starlette ships with FastAPI); **driver/protocol pattern** honored (`RateLimitStore` Protocol, swappable store); **no silent fallback** — bad config raises `ValueError` (hard error at build), and disabled → empty limiters → middleware explicitly omitted (an explicit off-switch, not a fallback). EUPL/license unaffected.
6. **Done = green** ✓ — `tests/test_rate_limit.py` 10/10 pass; pre-existing docker-dependent errors are unrelated (reproduced on `main`).

### Observations (non-blocking)
- The `/ask` limiter and `/metrics` exemption are configured, but neither route exists yet in `api.py`. This matches the change spec, which explicitly names `/ask` and `/metrics`, and is harmless (a limiter on a non-existent path simply never fires). Building forward to the named spec is within scope — not a defect.

No changes made — reviewer is read-only.
