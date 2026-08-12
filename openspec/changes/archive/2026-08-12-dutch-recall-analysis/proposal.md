## Why

The index used the built-in Dutch analyzer (stemming + stopwords), but Dutch is
compound-heavy and the stemmer does not split compounds: "kostenonderbouwing"
stems to `kostenonderbouw`, so a search for "kosten" (`kost`) never matches it,
and "subsidie" misses "subsidieaanvraag". Recall on real Dutch government text
suffers.

## What Changes

- The index text field is analysed with a custom Dutch analyzer (lowercase +
  asciifolding + Dutch stopwords + Dutch stemmer) for precision, **plus** an
  n-gram **recall sub-field** (`text.recall`) that indexes substrings so
  compounds/substrings match without a decompounding dictionary (searched with a
  whole-term analyzer, not n-grammed).
- BM25 search (and the BM25 arm of hybrid) query both fields via `multi_match`
  (`text^3, text.recall`): the stemmed field dominates ranking, the n-gram field
  adds recall.

## Capabilities

### Modified Capabilities
- `search`: document BM25 indexing/search gains Dutch compound recall via an
  n-gram sub-field queried alongside the stemmed field.

## Impact

- Code: `src/wordsworth/opensearch_index.py` (`_mapping` analysis + multi-field,
  `_bm25` query used by `search` and `hybrid_search`). Offline tests for the
  mapping/query shape.
- **Reindex required**: the mapping change applies to a newly created index only.
  The `wordsworth` index must be recreated and the corpus re-ingested for the new
  analysis to take effect (existing documents keep the old analysis until then).
