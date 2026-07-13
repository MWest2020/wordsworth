# Tasks — add-rag

Done = green: every task ships with its tests in the same builder run.
NOTE: unchecked — for a Habitat builder to implement.

## 1. Generator seam
- [ ] 1.1 `generator.py`: `Generator` protocol, `Source`, `Answer` (text +
      citations); `OllamaGenerator` (local LLM via stdlib HTTP, config URL+model);
      deterministic test double
- [ ] 1.2 Tests: injected generator is used; local-model-unavailable fails loudly
      (no cloud fallback)

## 2. RAG flow + grounding guard
- [ ] 2.1 `rag.py`: `ask(session, query, index, embedder, generator, k)` — hybrid
      retrieve -> build Source[] by fetching each passage via
      `get_anonymized_text(session, hit.document_id)` (hits carry no text) ->
      generate -> verify citations
- [ ] 2.2 Grounding guard: `valid = {s.document_id for s in sources}`; drop
      citations not in it; empty valid set -> "no grounded answer" result (never
      fabricated prose)
- [ ] 2.3 Tests: sources are exactly the top-k hybrid hits; source text is the
      de-identified `anonymized_text`; invented citation dropped; all-invalid ->
      ungrounded result

## 3. API
- [ ] 3.1 `GET /ask?q=` endpoint (session + generator + index + embedder injected)
- [ ] 3.2 Test: ask endpoint returns answer + verified citations

## 4. Config
- [ ] 4.1 Local LLM URL + model (Ollama) settings
