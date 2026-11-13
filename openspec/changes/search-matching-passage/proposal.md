# search-matching-passage

## Why

Mark, 2026-10-28: the key user wants to *"know which documents are
relevant"*. The review (docs/explanation/review-key-user-2026-10-28.md) found that a result's fragment is cut around the
first query word in the text (`console_data.fragment`); a semantic match without
a shared word falls back to the opening characters, usually a letterhead. The
index holds a vector for every passage of a document (408 documents carry
them), but the console does not use them. The bare score (a fused rank value)
invites comparisons it doesn't support.

## What changes

- For the hits on the page (ten at most), the console reads their passage
  vectors from the index, compares each with the question's vector, and shows
  **the passage of the document closest to the question**, cut from the stored
  pseudonymised text.
- The query words that occur in that passage are marked, and a short reason
  says what the passage shares with the question: "op woorden", "op
  betekenis", or both.
- The bare score moves to a tooltip.
- **The order of results does not change**, and nothing new is stored: no new
  index field, no mapping change, no backfill.
- When the passage cannot be determined, the result shows the fragment it
  shows today, and the page says so when the cause is the index.

## Amended 2026-11-13

The first version promised "the passage that ranked the document", taken from
the kNN inner hit, with passage offsets stored in the index and filled in by
`wordsworth-backfill-passages`. Checked against the code, none of that holds:

- Production does not rank by passage. `WORDSWORTH_HYBRID_KNN` is unset, so the
  default `document` applies (`config.py:422`); #190 measured the passage
  variant and did not switch. No passage ranks a document, and a hit that came
  in through BM25 only has no ranking passage in any setting.
- `passages.split` joins the words of a window with single spaces, so a
  passage is not a substring of the stored text and has no offsets.
- `wordsworth-backfill-passages` selects documents without passages
  (`missing_passages`). Every document has them, so it would select nothing.

So the offsets, the inner hit and the backfill are removed, and the wording
becomes "the passage closest to your question", which is true.

## Working assumptions (Mark can overrule)

- **Explain, don't re-rank (question M1).** The proposal used to promise the
  passage that ranked the document. Default: the result shows the passage
  closest to the question and the ranking stays exactly as it is; ranking by
  passage stays with #196. If Mark wants the shown passage to be the one that
  decided the rank, that is a ranking change and a different proposal.

## Out of scope

Changing the ranking itself, the embedding model, or the passage size.
Switching `WORDSWORTH_HYBRID_KNN`. The API's search answers: this change is
the console page.
