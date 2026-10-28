# Re-indexing keeps a document's topic assignment

## Why

The orchestrator, from the odin coding session, relaying Mark's mail: *"asking
by topic yields nothing."* The cause: *"reprocess (reanonymize) rewrites the
index entry without the topics field. All 408 documents had lost their topics,
and I recomputed them by hand (17 topics, 184 documents in a topic)."*

`index()` replaces the whole index entry, and the `topics` field is not part of
what `reanonymize` hands it, so every reprocessed document silently leaves its
topic. A search within a topic then finds nothing, with no error: the same
silent failure as the lost embeddings and dossiers of 2026-09-18.

Today this is written down as intended: the docstring of `OpenSearchIndex.index`
says dropping the topic is "juist" (a reprocessed document should not stay in a
group computed over its old text), and `docs/how-to/topics.md` says a document
that goes through the straat again "valt uit zijn onderwerp". That reasoning
did not survive a 408-document reprocess: the topic view still lists the topics
and their counts, while searching within them returns nothing. This reverses
that choice, which changes what searching within a topic promises, so it is an
OpenSpec change.

## What changes

- Re-indexing a document through `reanonymize` (and so `/reprocess` and
  `wordsworth reprocess`) keeps the topics the document had in the index.
- A test proves it: index a document, give it a topic, reprocess it, and search
  within that topic; the document is still found.
- The docs that say a reprocessed document drops out of its topic say the
  opposite.

Not changed: topic computation (still on request only), the rule that a topic
narrows and never scores, and which topics exist. Ingest of a document that is
not yet indexed has no topics to keep.

## Open questions

- Staleness. A kept topic was computed over the text from before the reprocess.
  The decision is to keep it; it does not say whether the topic view should show
  that members were reprocessed since `computed_at`. Until decided, the only
  signal is the `computed_at` and document count already stored with each
  topic, and a new computation (on request) replaces the assignment.
- Whether the idempotent re-index in `process` (a crash between index and
  commit) should keep topics as well. The decision names reanonymize/reprocess
  only; `process` is left as it is.
