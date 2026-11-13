---
status: current
last_reviewed: 2026-11-13
---

# Why a result matched: the closest passage, not the ranking passage

The search page shows, for each of the first ten hits, the passage of the
document closest to the question, with the query words in it marked and a
reason ("op woorden", "op betekenis", or both). This page explains what that
passage is, what it is not, and why the change behind it
(search-matching-passage) stores nothing. How to read the page is in
[the console how-to](../how-to/console.md#why-a-result-matched).

## Closest passage, not ranking passage

The first version of the proposal promised "the passage that ranked the
document", taken from the kNN inner hit. That is not true on the live setting:

- Production ranks on whole-document vectors. `WORDSWORTH_HYBRID_KNN` is unset,
  so the kNN half compares the question with each document's one embedding
  (`config.py`); #190 measured the passage variant and did not switch. No
  passage decided a document's rank.
- A hit that came in through BM25 only has no ranking passage in any setting.
- `Hit` carries no trace of which half of the hybrid search brought it in.

So the page claims what it can show: of this document's passages, this one is
closest in meaning to your question. The order of the hits is the ranking's
and does not change; the console asserts that in a test, with and without
passage vectors in the index. Ranking by passage stays with #196: that is a
ranking change and a proposal of its own.

## Why nothing is stored

Everything the page needs is already there:

- the passage vectors are in the index, one per window of the stored text
  (`wordsworth.passages`, 200 words every 150);
- the passage text is the stored pseudonymised text.

The offsets of a window follow deterministically from the text
(`passages.split_spans`, the same rule as `passages.split`), so they are
computed when the page is shown. Storing them would have meant a mapping
change and a backfill for something that can be derived, and one more thing to
keep in step after a reanonymisation. The shown text is `text[s:e]` of the
stored text, so it stays a quotation of what the index holds, never a
re-joined copy of it.

What the page does cost is one extra read: the passage vectors of the first
ten hits (an `mget`), and a second embedding of the question. The size of that
read is estimated in the how-to and measured at the demo rehearsal.

## When a passage is not shown

The passage is only as good as the match between the stored vectors and the
stored text. When the number of vectors differs from the number of windows
(indexed under another passage size, or the text changed without a reindex),
a vector may belong to another window and would point at the wrong words. The
hit then shows the fragment it showed before this change, without a reason.
When the index cannot be read for the passages, or the question cannot be
embedded a second time, every hit shows that fragment and the page says the
passages are unavailable. Neither is silent.

## Limits

- The closest passage is not the reason the document is at its rank, and the
  page does not say it is.
- A document can match on a word in one place while another passage is closer
  in meaning. The shown passage then may not hold that word, and the reason
  reads "op betekenis", which is true of the passage.
- The four-character rule for query words is a rule of thumb: it keeps "de"
  and "van" out, and also keeps out a short word that matters ("WOZ" is three).
- The OpenSearch `mget` is tested in CI on a small index. On the real index it
  is first exercised at the demo rehearsal.
- Rejected for now, first to reopen if the read is too heavy: a nested kNN
  over the shown ids with inner hits, which keeps the vectors on the server.
  Its behaviour depends on the k-NN engine and version of production's
  OpenSearch, which cannot be checked while it is unreachable, and it would
  need a second implementation of the same choice for the in-memory index.
