# Tasks — add-bm25-indexing

Done = green: every task ships with its tests in the same builder run.

## 1. Search seam
- [x] 1.1 `search_index.py`: `SearchIndex` protocol + `Hit` + `InMemoryIndex`
      (term-overlap scorer test double)
- [x] 1.2 Tests: index + search returns the doc; stronger match ranks higher;
      re-index same id does not duplicate

## 2. OpenSearch driver
- [x] 2.1 Add `opensearch-py` dependency
- [x] 2.2 `opensearch_index.py`: `OpenSearchIndex` — Dutch analyzer mapping,
      idempotent upsert by document id, BM25 search
- [x] 2.3 Config: OpenSearch URL + index name
- [x] 2.4 Integration tests (skip if no OpenSearch): index + keyword search,
      ranking order, no duplicate on re-index

## 3. Pipeline wiring
- [x] 3.1 `process()` gains injected `search_index` (defaults to OpenSearch)
- [x] 3.2 `index` transition real: push anonymized text + object_key, then
      transition; idempotent; index failure propagates (doc stays anonymized)
- [x] 3.3 Tests: e2e with InMemoryIndex -> indexed and searchable; index outage
      leaves doc in anonymized (retryable)

## 4. Search API
- [x] 4.1 `GET /search?q=` on the FastAPI app (search index injected)
- [x] 4.2 Test: search endpoint returns ranked hits

## 5. Regression
- [x] 5.1 Existing suites still pass (index step no longer a stub)
