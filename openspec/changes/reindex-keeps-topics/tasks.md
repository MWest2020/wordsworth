# Tasks

## 1. Keep the topics on re-index
- [x] `SearchIndex` protocol (`src/wordsworth/search_index.py`): an optional
      `topics` parameter on `index()` and a read of one document's topics, in
      `InMemoryIndex` and `OpenSearchIndex` (`src/wordsworth/opensearch_index.py`).
      Proved by: `tests/test_topics.py`, `index(..., topics=[...])` stores them
      and `index()` without `topics` stores none, as before.
- [x] `reanonymize` (`src/wordsworth/pipeline.py`) reads the document's topics
      before re-indexing and passes them to `index()`. Proved by:
      `tests/test_topics.py`, after `reanonymize` a topic-scoped `search` still
      returns the document.
- [x] End to end through reprocess: `reprocess` over a document in a topic, then
      a search within the topic finds it. Proved by: a test in
      `tests/test_topics.py`.
- [x] The OpenSearch driver writes the topics in the same `index` call. Proved
      by: a test on the body sent by `OpenSearchIndex.index` with a fake client.
- [x] A document that is not indexed yet reprocesses without topics and without
      error. Proved by: a test in `tests/test_topics.py`.
- [x] Update the docstring of `OpenSearchIndex.index` and the comment in
      `InMemoryIndex.index` ("zie OpenSearchIndex.index") that say the topic
      falls away. Proved by: `grep -n "onderwerp-lidmaatschap" src` finds only
      the new wording.

## 2. Docs (must change with the code)
- [x] `docs/how-to/topics.md`, "Wat dit niet doet": the line that a document
      going through the straat again "valt uit zijn onderwerp" now says the
      topic is kept, and that it was computed over the text from before the
      reprocess. Proved by: the line is changed.
- [x] `docs/how-to/topics.md`, "Zoeken binnen een onderwerp": a sentence that
      this keeps working after a reprocess. Proved by: the sentence is present.
- [x] `openspec validate reindex-keeps-topics --strict` passes.
