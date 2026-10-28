# search-matching-passage

## Why

Mark, 2026-10-28: the key user wants to *"know which documents are
relevant"*. The review (docs/explanation/review-key-user-2026-10-28.md) found that a result's fragment is cut around the
first query word in the text (`console_data.fragment`); a semantic match without
a shared word falls back to the opening characters, usually a letterhead. The
passage that ranked the document is known to the index (408 documents carry
passage vectors), but only as vectors without positions, so the console can't
show it. The bare score (a fused rank value) invites comparisons it doesn't
support.

## What changes

- The index stores, per passage, its start and end offset in the pseudonymised
  text next to its vector.
- Hybrid search returns, per hit, which passage scored best.
- The search result shows that passage (from the stored pseudonymised text),
  with the query terms that occur in it marked, and a short reason: "matched
  on these words", "matched on meaning", or both.
- The bare score moves to a tooltip; results keep their order.
- `wordsworth-backfill-passages` fills in offsets for documents indexed
  before this change.

## Out of scope

Changing the ranking itself, the embedding model, or the passage size.
