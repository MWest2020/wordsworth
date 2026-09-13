# hybrid-search Specification

## Purpose

Combining keyword and vector retrieval, and being explicit about which one decides.

Fusion tends to be where recall is claimed and precision is quietly lost, so the
division of labour is pinned down: **RRF fuses for recall**, and **the Zeef cosine
is the final selector**. One stage is allowed to be generous; exactly one stage
decides what is returned.

Embedding is **local with hard failure**. Falling back to keyword-only on an
embedding outage would return plausible results that answer a different question
than the one asked, and nothing in the output would say so.
## Requirements
### Requirement: Local embedding with hard failure

Embeddings SHALL be produced through an `Embedder` protocol backed by local
inference (Ollama/bge-m3); no cloud in the critical path. A failed embedding
SHALL raise an error and SHALL NOT return or store a null/zero vector.

#### Scenario: Failed embedding raises, never nulls

- **WHEN** an embedding cannot be produced (backend error or empty input)
- **THEN** an `EmbeddingError` is raised and no zero vector is returned

#### Scenario: Same text embeds deterministically (test double)

- **WHEN** the deterministic embedder embeds the same text twice
- **THEN** it returns the identical vector of the configured dimension

### Requirement: RRF recall fusion

BM25 and kNN rankings SHALL be fused with Reciprocal Rank Fusion to form the
recall candidate set.

#### Scenario: Ranking high in both inputs wins

- **WHEN** a document ranks near the top of both the BM25 and the kNN list
- **THEN** it ranks above a document that ranks in only one

### Requirement: Zeef cosine is the final selector

The final ranking over the recall set SHALL be `zeef.similarity.cosine` between
the query embedding and each document embedding — the proven "--no-llm + cosine"
path. No LLM scoring and no clustering SHALL influence the ranking.

#### Scenario: Relevant document ranks first

- **WHEN** a hybrid search is run for a query strongly matching one document
- **THEN** that document is ranked first, scored by cosine similarity

### Requirement: Hybrid search over the API

Hybrid search SHALL be exposed as `GET /hybrid?q=`, returning ranked hits without
exposing raw vectors.

#### Scenario: Hybrid endpoint returns ranked hits

- **WHEN** `GET /hybrid?q=<terms>` is called
- **THEN** it returns the ranked hits, and no raw vector is included in the payload

