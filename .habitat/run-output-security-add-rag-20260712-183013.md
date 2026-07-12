# Habitat security — add-rag

_run_id security-add-rag-20260712-183013 · verdict ok · 2026-07-12T18:32:44Z_

---

All three security checks are complete. I have my verdict.

---

## Security verdict — change `add-rag`: **PASS** ✅

Judged against `CLAUDE.md` + the change only. Read-only; no files modified.

### 1. Secrets scan — PASS
- Full `main...HEAD` diff scanned for keys/tokens/private-keys/`.env`/hardcoded creds. The only regex hits (`config.py:168,173`) are false positives — the substring `.env` inside `os.environ.get(...)`. Both are safe env-var reads with non-secret defaults (`WORDSWORTH_EMBEDDING_DIM=1024`, `WORDSWORTH_LLM_MODEL=llama3.1`).
- No key material (`sk-…`, `ghp_`, `xox…`, PEM blocks) anywhere in `src/`.

### 2. Forbidden dependencies — PASS
- No `anonypy`, `MinIO`, CyberArk/Conjur, or AGPL (`PyMuPDF`/`fitz`) referenced in the diff.
- No dependency manifest (`pyproject`/`uv.lock`/`requirements`) changed — RAG reuses stdlib `urllib` for the local Ollama call; **no cloud client added**, consistent with the "no cloud APIs in the critical path" invariant (`OllamaGenerator`, and `GenerationError` enforces loud failure — no silent fallback).

### 3. Audit hash-chain integrity — PASS
- The only audit artifact this change adds is the genesis `.habitat/audit.jsonl` entry. I reproduced its hash deterministically: `sha256("|".join(FIELDS))` = `08764b22…efd9ee`, matching the stored `entry_hash`; `prev_hash=""` correctly links a genesis entry. **Chain verifies end-to-end.**
- The DB append-only audit chain code (`audit.py`, `models.py`, `hashing.py`) is **untouched** by this change. RAG is a query-only feature that writes no audit records → DB chain integrity preserved by construction.

### Supporting notes
- **Ownership guard:** no diff to `CLAUDE.md`, `.claude/agents/`, or CI config.
- **No clear PII to the model:** `rag.ask` builds `Source` objects only from de-identified index text (`Hit.text`), never raw text; `test_rag.py` asserts this — honors the PII invariant.
- **Tests:** 12 RAG/generator/API tests pass. The 4 `test_audit.py` errors are environment-only (`FileNotFoundError: 'docker'` — Postgres testcontainer unavailable here), unrelated to this change and not touching any audit code.
- **Limitation (non-blocking):** the entry's `diff_hash` field is the builder's own attestation over its diff scope; I couldn't reproduce it with naive `git diff` candidates (base/scope convention unknown). This does not affect the verdict — `entry_hash` validity confirms the record is internally consistent (unmutated after hashing), and I independently reviewed the actual diff contents for checks 1–2.
