# Habitat reviewer — add-rag

_run_id reviewer-add-rag-20260712-182814 · verdict ok · 2026-07-12T18:30:09Z_

---

Review complete. Here is my verdict.

---

## Reviewer verdict: **PASS** — change `add-rag`

Reviewed the builder diff (`39358e1`) against `CLAUDE.md` and `openspec/changes/add-rag/` only.

### Checks

1. **Scope ✓** — Diff implements exactly the change's tasks: `Generator` protocol + `OllamaGenerator` + `DeterministicGenerator` test double (`generator.py`), the retrieve→generate→verify flow (`rag.py`), the `GET /ask` endpoint (`api.py`), and Ollama LLM-model config (`config.py`). The `Hit.text` additions to `search_index.py:23` / `opensearch_index.py:80` are the minimal plumbing needed to hand de-identified passage text to the generator — in-scope per tasks 2.1. Nothing outside the change.

2. **No clear PII toward index/model ✓** — RAG reads only the existing index `text` field (already de-identified in prior phases); no raw-document path is introduced. `_hit` (`api.py:70`) still omits raw vectors. `test_sources_carry_deidentified_index_text` locks the source text to index text. Proposal/design boundary honoured.

3. **No mutable audit tables ✓** — no audit schema or state changes; `current_state` derivation untouched.

4. **No cloud APIs in critical path ✓** — `OllamaGenerator` targets the local Ollama URL; on any network/HTTP/parse failure it raises `GenerationError` (`generator.py:79`) with no fallback. `test_local_model_unavailable_fails_loudly_no_cloud_fallback` proves the loud failure — satisfies the no-silent-fallback invariant.

5. **CLAUDE.md invariants ✓** — `uv` used (not pip); files ≤200 lines (generator 97, rag 41, api 70); driver/protocol pattern followed; no new dependencies (stdlib `urllib` only, so no license/banned-dep exposure); no silent fallbacks.

6. **Done = green ✓** — the change's tests pass: `test_rag.py`, `test_generator.py`, `test_api.py` → **12 passed**. Full suite: 57 passed / 5 skipped; the 22 errors are all `FileNotFoundError: 'docker'` in unrelated testcontainer-backed suites (pipeline, mapping_store, pseudonymizer) — an environment limitation, not touched by this change.

### Hard-fail check
No diff to `CLAUDE.md`, `.claude/agents/`, or CI config. ✓

**PASS.** The security agent may now run.
