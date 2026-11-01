# Design

## Where the topics go

Topic membership lives only in the index (`topics` keyword field); the database
holds the description. `index()` writes the whole entry, so anything the caller
does not pass is gone. `reanonymize` passes text, vector, dossiers and passages,
not topics.

## Choice: read the topics first, write them in the same index call

`reanonymize` reads the document's current topics from the index before
re-indexing and passes them to `index(..., topics=...)`. One write, so there is
no moment in which the document is indexed without its topics, and no second
write that can fail separately.

This needs one small read on the `SearchIndex` protocol (the topics of one
document; an empty list when it is not indexed) and an optional `topics`
parameter on `index()`, implemented in `OpenSearchIndex` and `InMemoryIndex`.
`index()` without `topics` behaves as today, so ingest is unchanged.

The existing methods are not enough: `documents_in` reads by dossier, not by
document.

## Rejected alternatives

- **Re-index, then call `set_topics` with what was read.** Two writes; a failure
  between them leaves the document topic-less, which is the bug again, now
  intermittent.
- **Recompute topics for the dossier after every reprocess.** Topics are on
  request on purpose (a quadratic cost for an answer nobody reads yet), and it
  would replace the generation a person may have renamed.
- **Make `index()` always preserve existing topics.** Convenient, but it hides
  the rule inside the seam. A caller that really wants a topic-less entry could
  no longer say so, and the lesson of 2026-09-18 is that the caller states what
  is kept.
- **A partial update for reanonymize** (touch only text, vector, passages). It
  would also keep dossiers and topics, but it changes how every field is
  written for a bug in one; larger than the decision.

## Tests

The proof is a test through the real path: `reanonymize` against the in-memory
index with a topic set, then a topic-scoped search that still returns the
document. For the OpenSearch driver, a test on the body that `index()` sends.
