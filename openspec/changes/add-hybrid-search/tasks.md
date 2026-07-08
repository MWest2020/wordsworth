# Tasks — add-hybrid-search

Done = green: every task ships with its tests in the same builder run.

## 1. Embedding seam
- [x] 1.1 Add `zeef @ git` dependency (reuse `zeef.similarity`)
- [x] 1.2 `embedder.py`: `Embedder` protocol, `EmbeddingError`, `OllamaEmbedder`
      (bge-m3, stdlib HTTP), `DeterministicEmbedder` (stable hashing test double)
- [x] 1.3 Tests: deterministic + correct dim; failed/empty -> EmbeddingError (no null)

## 2. RRF fusion
- [x] 2.1 `rrf.py`: `reciprocal_rank_fusion` + `fuse_ranked_ids` (pure)
- [x] 2.2 Tests: high-in-both wins; union covered; top ranks score higher

## 3. Vector storage + hybrid recall
- [x] 3.1 `SearchIndex`: optional vector on index, `hybrid_search` recall; extend Hit
- [x] 3.2 `InMemoryIndex`: store vectors, hybrid_search (lexical + cosine kNN, RRF)
- [x] 3.3 `OpenSearchIndex`: knn_vector mapping (cosine/hnsw/lucene), store vector,
      hybrid_search (BM25 + kNN queries, RRF, mget vectors)
- [x] 3.4 Integration tests (skip if no OpenSearch): hybrid ranks relevant first

## 4. Zeef ranking
- [x] 4.1 `hybrid.py`: embed query, RRF recall, final order via zeef.similarity.cosine
- [x] 4.2 Tests: relevant first; final score is cosine (identical text -> 1.0)

## 5. Pipeline + API
- [x] 5.1 `process()` gains injected `embedder`; index step embeds + stores vector
- [x] 5.2 `GET /hybrid?q=` endpoint (no raw vectors in payload)
- [x] 5.3 Tests: pipeline indexes a vector; hybrid endpoint ranks hits
- [x] 5.4 Existing process() tests inject the deterministic embedder

## 6. Config
- [x] 6.1 Ollama URL, embedding model, embedding dimension
