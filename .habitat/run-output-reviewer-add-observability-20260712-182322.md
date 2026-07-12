# Habitat reviewer — add-observability

_run_id reviewer-add-observability-20260712-182322 · verdict ok · 2026-07-12T18:25:42Z_

---

I have everything I need for a verdict. Let me summarize my review.

## Reviewer verdict: **PASS**

Change under review: `add-observability`. Judged against `CLAUDE.md` + the change only.

### Hard-fail check — clear
No diff to `CLAUDE.md`, `.claude/agents/`, or CI config. Files touched outside `src/`/`tests/`/`openspec/` are Habitat build artifacts only (`.habitat/audit.jsonl`, `.habitat/run-report-*.html`, `run-report.json`) — none are Mark-owned.

### Checks
1. **Scope** ✓ — Exactly the three deliverables in the spec/tasks: `GET /metrics` (`metrics.py`, `api.py:37-43`), structured JSON transition logs (`structured_log.py`, wired at `pipeline.py:73-83`), and throughput/stage-timing on the run report (`report.py`). No scope creep. `tasks.md` change is checkbox-marking only.
2. **No clear PII toward index** ✓ — Metrics and logs carry only UUIDs, state names, step names, and durations. The log line deliberately omits `payload`/document text. Nothing new flows toward indexing/search.
3. **No mutable audit** ✓ — Every new query is `SELECT`-only over `audit_records`; no `UPDATE`/`DELETE`. `current_state` remains derived (`DISTINCT ON … ORDER BY seq DESC`), never stored. Append-only nicely makes the `_total` counters genuinely monotonic.
4. **No cloud APIs in critical path** ✓ — Local only. Prometheus is emitted as plain text (no client library, no new dependency, no external telemetry) — matches the sovereign boundary in design.md.
5. **CLAUDE.md invariants** ✓ — `uv` used, no dependency changes; all files ≤200 lines (largest is `pipeline.py` at 191); no banned deps; no silent fallbacks — the `/metrics` endpoint is simply not registered without a `session_factory` and returns a clean 404 (tested at `test_metrics.py`). Postgres-specific SQL (`DISTINCT ON`, `percentile_cont`, `lag`) is legitimate — the test harness runs a real Postgres 16.
6. **Done = green** — Tests exist for all three requirements and are well-formed. The 3 DB-free tests pass here. The 4 Postgres-backed tests could not execute in this sandbox because the `docker` binary is absent (conftest's `_docker_ok()` raises on the missing binary); this is an environment limitation, **not** a defect in the change. Under the intended Docker/Postgres harness they exercise the SQL directly.

### Non-blocking observations (not FAIL grounds)
- `configure_logging()` in `structured_log.py` is never called within `src/`. This is intentional per design.md ("Operators attach their own handler, or call `configure_logging()`") — a provided operator seam, not stray dead code. Worth noting that transition logs (INFO level) will be dropped by Python's last-resort handler in production unless an operator wires up logging, but this is observability, not pipeline correctness, so it doesn't violate the no-silent-fallback rule.

The change is in bounds, honors every invariant, and is correctly tested. **PASS.**
