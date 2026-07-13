# Design decisions — add-rag

## The rule: LLM advises, deterministic decides

- **Retrieval decides the sources.** Hybrid search (deterministic: RRF recall +
  zeef cosine) selects the top-k candidate passages. The LLM never chooses what is
  relevant; it only phrases an answer over what retrieval handed it.
- **Citations are verified, not trusted.** The generated answer must cite source
  document ids; a deterministic guard intersects the cited ids with the retrieved
  set and **drops any citation not in it**. An answer whose citations are all
  invalid (or empty) is reported as "no grounded answer", never fabricated prose.
- This is why RAG is safe to add: the deterministic layer is authoritative; the
  LLM is a phrasing convenience that cannot smuggle in ungrounded claims.

## Seam

```python
@dataclass
class Source:
    document_id: str
    text: str            # de-identified passage handed to the model

@dataclass
class Answer:
    text: str
    citations: list[str]  # verified subset of the source document ids

class Generator(Protocol):
    def generate(self, query: str, sources: list[Source]) -> Answer: ...
```

- `OllamaGenerator`: local LLM via Ollama (stdlib HTTP), prompted to answer ONLY
  from the given sources and to cite their ids. Model/URL from config.
- Deterministic test double: returns a fixed answer citing given source ids, so
  the flow and the grounding guard are testable without a model.

## Flow

`ask(session, query, index, embedder, generator, k)`:
1. `hits = hybrid_search(index, embedder, query, size=k)` — deterministic sources.
2. Build `Source[]`: hits carry `document_id` but NOT text, so fetch each
   passage from the de-identified store —
   `get_anonymized_text(session, hit.document_id)` (reuse, don't re-query the
   index). This is why `ask` takes a `session`.
3. `answer = generator.generate(query, sources)`.
4. **Guard**: `valid = {s.document_id for s in sources}`;
   `answer.citations = [c for c in answer.citations if c in valid]`.
   If empty and the answer asserts content, return a "no grounded answer" result.
5. Return the answer + verified citations.

## Boundaries (invariants honoured)

- **No cloud**: local LLM only; unavailable model -> loud failure, no fallback.
- **No clear PII to the model**: sources come from the anonymized/pseudonymized
  index, never raw text.
- **Optional**: opt-in `GET /ask?q=`; pipeline/search unchanged.

## Not in scope

Multi-turn chat, answer caching, streaming, and any LLM-as-decider behaviour
(e.g. letting the model re-rank or filter sources — that would violate "the LLM
advises, deterministic decides"). Query-time audit logging of answers is a
possible follow-up, not required here.
