## Why

Optional, after-MVP: let a user ask a question and get a written answer **with
source references**, grounded in the corpus. wordsworth already retrieves and
ranks; RAG adds a phrasing layer on top. The rule that keeps it trustworthy:
**the LLM advises, deterministic decides** — retrieval (deterministic) chooses the
sources, the local LLM only phrases an answer over them, and every citation is
verified against the retrieved set. Local model only; no cloud in the critical
path.

## What Changes

- Introduce a **`Generator` protocol** (driver/protocol pattern) with a local
  **`OllamaGenerator`** (local LLM) and a deterministic test double. No cloud.
- Add a **RAG flow**: retrieve top-k via existing hybrid search → build a prompt
  from those (already de-identified) passages → generate an answer that cites the
  source document ids.
- **Deterministic grounding guard**: the answer's citations MUST be a subset of
  the retrieved source ids; any invented citation is rejected. If no valid source
  supports an answer, the system says so rather than fabricate.
- Operate only over the **anonymized/pseudonymized** index text, so no clear PII
  ever reaches the model.
- Expose it as an opt-in API endpoint (`GET /ask?q=`), returning the answer and
  its verified citations.

## Capabilities

### New Capabilities
- `rag`: the `Generator` seam, the retrieve→generate flow, the deterministic
  citation-grounding guard, and the ask API.

### Modified Capabilities
<!-- none: RAG is additive, consuming hybrid search and the de-identified index. -->

## Impact

- New module surface: `generator`, `rag`; config for the local LLM (Ollama URL +
  model). Reuses hybrid search for retrieval. Because hits carry no passage text,
  `ask` takes a session and resolves each source's text from the de-identified
  `DocumentText.anonymized_text` (reusing `get_anonymized_text`).
- Local LLM only; if the model is unavailable the endpoint fails loudly (no cloud
  fallback). The LLM never sees clear PII (index is de-identified).
- Optional feature; the pipeline and search paths are unchanged. Does not touch
  `CLAUDE.md`, `.claude/agents/`, or CI.
