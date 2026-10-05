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

### Requirement: The final ranking does not shut out long documents

The final ranking over the recall set SHALL keep the fused RRF rank of the BM25
and kNN recall lists. It SHALL NOT re-sort them by cosine against one embedding
per whole document: on the Woo measurement collection of change
`long-documents-rank-fairly` that re-sort found not one of the longest third of
documents by its own title (Recall@8 0.000). With the fused rank, Recall@8 SHALL
be above zero in every length third, and every change to ranking SHALL record
the values per third on that collection. No LLM scoring and no clustering SHALL
influence the ranking.

Known limitation, measured 2026-10-05 on the full index and accepted by Mark the
same day: the longest third is still found less often than the shortest
(Recall@8 0.400 against 0.731). Ranking by best passage closed the gap but
flipped the bias, filling the top 8 with long documents and missing the
windpark question; that variant is not the default.

#### Scenario: Relevant document ranks first

- **WHEN** a hybrid search is run for a query strongly matching one document
- **THEN** that document is ranked first

#### Scenario: A long document that answers is among the sources

- **WHEN** `/ask` is asked "Welke afspraken zijn gemaakt over het windpark en
  de natuurcompensatie"
- **THEN** a document containing "windpark" is among the top 8 hybrid hits

#### Scenario: No length third is shut out

- **WHEN** the ranking is measured on the Woo collection
- **THEN** Recall@8 is above zero for the short, middle and long third alike

### Requirement: Hybrid search over the API

Hybrid search SHALL be exposed as `GET /hybrid?q=`, returning ranked hits without
exposing raw vectors.

#### Scenario: Hybrid endpoint returns ranked hits

- **WHEN** `GET /hybrid?q=<terms>` is called
- **THEN** it returns the ranked hits, and no raw vector is included in the payload
