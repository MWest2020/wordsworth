# Tasks — fix-caching-recall-key

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
Fixes #20 (part 1).

## 1. Query cache key includes recall
- [ ] 1.1 `query_key`/`cached_query` include `recall` (and every other
      output-affecting param) in the key
- [ ] 1.2 Tests: same query+size but different `recall` → distinct keys; neither
      serves the other's result
