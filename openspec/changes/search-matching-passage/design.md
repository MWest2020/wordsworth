# Design: search-matching-passage

## Decisions

- **Store nothing new.** The passage vectors are in the index already, and the
  passage text is the stored pseudonymised text. Both are read at the moment a
  page is shown. Nothing new to scrub, to migrate or to keep in step.
- **Read the vectors of the shown hits only.** One new read on the index
  protocol, `SearchIndex.passages_of(ids) -> dict[str, list[list[float]]]`, on
  `InMemoryIndex` and `OpenSearchIndex` (an `mget` with
  `_source=["passages.vector"]`, at most ten ids). It is wrapped as a read, so
  a transport failure is `SearchUnavailable`. `opensearch_index.py` is 443
  lines: the body goes in a new `passage_reads.py`.
- **Offsets come from the text, deterministically.**
  `passages.split_spans(text) -> list[tuple[int, int]]` gives the same windows
  as `passages.split`, as character offsets into the text. The invariant, and
  its test: for every span, `" ".join(text[s:e].split())` equals the passage
  `split` returns at that position. The fragment is `text[s:e]`, so it stays a
  quotation of the stored text.
- **The closest passage.** `console_passage.best(text, vectors, query_vector,
  query) -> dict | None`: cosine of each passage vector with the question's
  vector (`zeef.similarity.cosine`, as `hybrid.py` uses), the winning span,
  the query words found in it, and the reason. The question's vector is the
  one the search used; where hybrid search does not hand it out, the console
  embeds the question once more with the same embedder. No code that decides
  the order of hits changes.
- **The reason describes the shown passage, not the rank.** Which half of the
  hybrid search brought a hit in is not recorded (`Hit` carries no trace of
  it), so the page does not claim it. It says what can be checked on the page:
  - "op woorden en betekenis": the passage is the closest in meaning and holds
    at least one query word;
  - "op betekenis": the passage is the closest in meaning and holds no query
    word; nothing is marked;
  - "op woorden": the search ran without an embedder (keyword search), so
    there is no question vector; the fragment is today's, around the first
    query word.
  A query word counts when it has four characters or more, so that "de" and
  "van" neither get marked nor turn every reason into "both". That is a rule
  of thumb, stated in the docs as one.
- **When the passage cannot be determined, today's fragment is shown and it is
  not silent.**
  - The number of stored vectors differs from the number of windows
    `split_spans` gives for the stored text (indexed under another passage
    size, or the text changed without a reindex): `best` returns `None`, the
    hit shows today's fragment without a reason.
  - `passages_of` raises `SearchUnavailable`: every hit shows today's fragment
    and the page says the passages are unavailable. The results themselves
    are still shown: they were already fetched.
  - A document without passage vectors: as the count mismatch.
- **The score moves to a `title` attribute.** It is still reported per hit, as
  the console requirement "The corpus can be searched from the console" asks,
  and the fragment is still a quotation of the pseudonymised text; that
  requirement is not modified.

## Where the code goes

- `passages.py`: `split_spans`;
- `search_index.py`, `opensearch_index.py`: `passages_of`, body in new
  `passage_reads.py`;
- new `console_passage.py`: `best`;
- `console_search.py` (173 lines), `templates/search.html`: show it.

## Rejected

- **Offsets stored in the index** (the first version): a mapping change and a
  backfill for something that can be computed from the stored text.
- **The kNN inner hit as "the passage that ranked the document"**: production
  ranks on whole-document vectors, so there is no such passage.
- **Switching to passage ranking so the promise becomes true**: a ranking
  change, measured in #190 and deliberately not made; it belongs to #196.

## Limits

- The closest passage is not the reason the document is at its rank, and the
  page does not say it is.
- For a document that matched on a word in one place while another passage is
  closer in meaning, the shown passage may not hold that word. The reason then
  reads "op betekenis", which is true of the passage.
- The OpenSearch `mget` is tested in CI on a small index. On the real index it
  is first exercised at the demo rehearsal.
