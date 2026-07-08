## Why

Fase 4: dense retrieval + hybrid fusion on top of BM25 — the configuration
Pilkes' thesis found best (ES-KNN won on Recall@10 and MAP). We add local dense
embeddings, fuse BM25 and kNN with RRF for recall, and use Zeef's cosine as the
final selector (the proven "--no-llm + cosine" path). Embeddings and ranking stay
local and sovereign; no cloud in the critical path.

## What Changes

- Introduce an **`Embedder` protocol** with a local **`OllamaEmbedder`** (bge-m3)
  and a **`DeterministicEmbedder`** test double. A failed embedding is a **hard
  error** (`EmbeddingError`) — never a null-vector fallback (nulvector-gap).
- Store a **kNN vector** per document in OpenSearch (`knn_vector`, cosine space)
  alongside the BM25 text; the `SearchIndex` protocol gains an optional vector and
  a `hybrid_search` recall method.
- Add **RRF fusion** (`rrf.py`) of the BM25 and kNN rankings for recall.
- **Reuse Zeef as the ranking component**: `zeef.similarity.cosine` is the final
  selector over the RRF recall set (`hybrid.py`). No LLM, no clustering.
- Make the **`index` transition embed** the anonymized text and store the vector
  (failed embedding is transient, like an index outage).
- Expose **hybrid search over the API** (`GET /hybrid?q=`).

## Capabilities

### New Capabilities
- `hybrid-search`: the `Embedder` seam, RRF fusion, Zeef cosine as final ranker,
  and the hybrid API.

### Modified Capabilities
- `search`: the `SearchIndex` protocol stores an optional vector and adds
  `hybrid_search`; OpenSearch gains a kNN field.
- `document-lifecycle`: the `index` transition also embeds and stores the vector.

## Impact

- New dependency: **`zeef @ git+https://github.com/MWest2020/zeef`** (Mark's repo;
  not on PyPI — the PyPI `zeef` is unrelated. TODO: publish under a free name and
  switch to a versioned dep). Reuses `zeef.similarity` (pure-Python cosine/tokenize).
- New module surface: `embedder`, `rrf`, `hybrid`; config for Ollama URL, model,
  and embedding dimension.
- `pipeline.process()` gains an injected `embedder` (defaults to Ollama).
- Ollama is not runnable in the build env, so `OllamaEmbedder` integration is not
  exercised here; hybrid is tested with the deterministic embedder against real
  OpenSearch (kNN). Does not touch `CLAUDE.md`, `.claude/agents/`, or CI.
