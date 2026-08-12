## 1. Analysis + query

- [x] 1.1 `_mapping`: custom Dutch analyzer (lowercase, asciifolding, stopwords,
  stemmer) + n-gram recall sub-field (`text.recall`, index n-grams / whole-term
  search analyzer) + `max_ngram_diff`.
- [x] 1.2 `_bm25` multi_match over `text^3` + `text.recall`; used by `search` and
  `hybrid_search`.

## 2. Gate + rollout

- [x] 2.1 Offline tests for mapping + query shape; full suite green.
- [ ] 2.2 Reindex on deploy: recreate the `wordsworth` index + re-ingest the
  corpus (mapping change only affects a new index).
