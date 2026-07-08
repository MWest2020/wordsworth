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
- [ ] 2.1 `rag.py`: `ask(query, index, embedder, generator, k)` — hybrid retrieve
      -> build Source[] from de-identified hit text -> generate -> verify citations
- [ ] 2.2 Grounding guard: drop citations not in the retrieved source ids; empty
      valid set -> "no grounded answer" result (never fabricated prose)
- [ ] 2.3 Tests: sources are exactly the top-k hybrid hits; invented citation
      dropped; all-invalid -> ungrounded result; sources carry de-identified text

## 3. API
- [ ] 3.1 `GET /ask?q=` endpoint (generator + index + embedder injected)
- [ ] 3.2 Test: ask endpoint returns answer + verified citations

## 4. Config
- [ ] 4.1 Local LLM URL + model (Ollama) settings
