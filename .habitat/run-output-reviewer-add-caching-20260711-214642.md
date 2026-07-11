# Habitat reviewer — add-caching

_run_id reviewer-add-caching-20260711-214642 · verdict ok · 2026-07-11T21:48:50Z_

---

Everything I need is confirmed. The 22 errors are environmental (`FileNotFoundError: 'docker'` — testcontainers unavailable in this sandbox), present across unrelated modules and wholly independent of this change, which touches only `cache.py` and `test_cache.py`. Here is my verdict.

---

## Reviewer verdict — `add-caching`: **PASS**

Reviewed the diff (`git diff main...HEAD`) against `CLAUDE.md` + the change under `openspec/changes/add-caching/` only.

**Diff surface:** `src/wordsworth/cache.py` (new, 122 L), `tests/test_cache.py` (new, 184 L), `openspec/changes/add-caching/tasks.md` (checkboxes), plus builder-generated habitat artifacts (`.habitat/audit.jsonl`, run-report HTML/JSON).

### Checks
1. **Scope ✓** — Implements exactly the three tasks: `Cache` protocol + bounded `LruCache` (1.x), `CachingEmbedder` keyed `emb:{model}:{sha256(text)}` (2.x), `cached_query` keyed `q:{mode}:{size}:{query}` with `invalidate`/`bypass` (3.x). Nothing outside the change in `src/`/`tests/`.
2. **No clear PII toward index ✓** — In-memory optimization seam only; wraps the existing local embedder and a recompute callable. No new indexing/search write path.
3. **No mutable audit tables ✓** — Untouched.
4. **No cloud APIs in critical path ✓** — Cache is in-memory; embedding cache delegates to the existing local `Embedder`. No network.
5. **CLAUDE.md invariants ✓** — `uv` used; both files ≤ 200 lines; no new dependency, no banned deps; driver/protocol pattern (`Cache` Protocol + `LruCache` impl); **no silent fallback** — a miss recomputes, and a failed embedding raises *before* any store (`cache.py:84-89`), so failures are never cached (composes with the nulvector rule).
6. **Done = green ✓** — `tests/test_cache.py`: 16 passed. The 22 suite-wide errors are `FileNotFoundError: 'docker'` in unrelated testcontainer-backed modules — environmental, not introduced by this change.

### Hard-fail check
No diff to `CLAUDE.md`, `.claude/agents/`, or CI config. ✓

### Non-blocking observations (not defects; no invariant/spec breach)
- The change ships the caching **seam** (wrapper class + helper) with a full contract test, but does not yet wire `CachingEmbedder`/`cached_query` into the live search/hybrid call sites. This matches the proposal's framing ("new module surface: `cache`") and every spec scenario is satisfied and tested — so it passes. Flagging only so a follow-up change knows the call-site integration is still open.
- `invalidate` is added to the `Cache` Protocol beyond the literal get/set snippet in `design.md`; this is consistent with the spec's "Invalidation/bypass SHALL be available" requirement.

**Verdict: PASS.** Proceed to the security agent.
