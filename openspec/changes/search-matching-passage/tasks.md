# Tasks

## 1. Index
- [ ] Passages carry `start`/`end` offsets into the pseudonymised text, written
      at indexing and by `wordsworth-backfill-passages`. Proved by: a test that
      an indexed document's passages map back to substrings of its stored text.
- [ ] Hybrid search returns the best passage per hit. Proved by: a test with a
      document whose second passage holds the answer: that passage is returned.
## 2. Console
- [ ] A result shows the best passage with query terms marked and the reason;
      without offsets it shows today's fragment. Proved by: console tests for
      both.
- [ ] The score moves to a tooltip; order unchanged. Proved by: a test.
## 3. Backfill and docs
- [ ] Run note: backfilling offsets on the live index (how long, how to check).
- [ ] `docs/how-to/console.md` and `docs/explanation` on why a result is
      relevant.
