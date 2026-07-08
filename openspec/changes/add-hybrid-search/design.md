# Design decisions — add-hybrid-search

## Retrieval shape: RRF for recall, zeef cosine for selection

```
query --embed--> qvec
  BM25(query)  ─┐
               ├─ RRF fuse (recall set) ── zeef.similarity.cosine(qvec, docvec) ── final order
  kNN(qvec)   ─┘
```

- **RRF** (`1/(k+rank)`, k=60) fuses the BM25 and kNN rankings into one recall
  set — backend-agnostic, pure, trivial to audit (`rrf.py`).
- **Zeef cosine is the selector**, matching the prompt's proven "--no-llm +
  cosine" path: recall broadly (hybrid), order by cosine. We reuse
  `zeef.similarity.cosine` (pure-Python, dependency-free) — the heart of Zeef's
  ranking — not its Woo-specific pipeline, and never its LLM rerank/score stages.

OpenSearch's kNN already ranks by cosine, so the final zeef pass correlates with
it; the point is that the *authoritative selector* is Zeef's audited cosine, with
OpenSearch used for candidate generation (recall).

## Embeddings: local, hard-fail, seam

- `Embedder` protocol; `OllamaEmbedder` (bge-m3, local HTTP, stdlib urllib — no
  new runtime HTTP dep). A failed embedding raises `EmbeddingError`; an empty/null
  vector is never returned or stored (nulvector-gap).
- `DeterministicEmbedder`: a stable hashing embedder for tests — reproducible
  (hashlib, not salted `hash()`), non-null, shared tokens share dimensions so kNN
  and cosine behave meaningfully without a model. Ollama is not runnable in the
  build env, so this is how hybrid is exercised against real OpenSearch.

## OpenSearch kNN

`knn_vector` field, `dimension` = embedding dim (bge-m3 = 1024; tests use 64),
`method` hnsw / `space_type` cosinesimil / `engine` lucene. Index setting
`index.knn: true`. `hybrid_search` runs BM25 and kNN as two queries, RRF-fuses the
id lists, then `mget`s the candidates' vectors so the upstream zeef cosine pass
can rank them.

## Pipeline: embed at index time

The `index` transition embeds the anonymized text and stores `(text, object_key,
vector)`. A failed embedding is transient (like an index outage): it propagates,
nothing commits, the document stays for retry — never a null vector, never
`failed`.

## Dependency: reuse Zeef now (Mark's call)

Depend on `zeef @ git` rather than reimplement cosine. Zeef is not on PyPI (name
taken); TODO on the Zeef project: publish under a free name, then switch this to a
versioned PyPI dep. **Clever pitfall noted:** pulling Zeef's whole pipeline — we
import only `zeef.similarity`, the small audited core.
