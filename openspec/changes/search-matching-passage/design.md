# Design: search-matching-passage

## Decisions

- **Store nothing new.** The passage vectors are in the index already, and the
  passage text is the stored pseudonymised text. Both are read at the moment a
  page is shown. Nothing new to scrub, to migrate or to keep in step.
- **Read the vectors of the shown hits only.** One new read on the index
  protocol, `SearchIndex.passages_of(ids) -> dict[str, list[list[float]]]`, on
  `InMemoryIndex` and `OpenSearchIndex` (an `mget` with
  `_source=["passages.vector"]`). It is wrapped as a read, so a transport
  failure is `SearchUnavailable`. `opensearch_index.py` is 443 lines: the body
  goes in a new `passage_reads.py`.
- **Ten ids at most, enforced in the read.** The console's search takes a
  `size` from the URL, so "the hits on the page" is not ten by itself.
  `passages_of` refuses more than ten ids (`ValueError`), and the console
  passes the first ten hits; a hit after the tenth shows today's fragment
  without a reason.
- **The payload is estimated here and measured in use.** A passage vector has
  1024 numbers (bge-m3), about 10 kB as JSON. A passage is a 200-word window
  every 150 words, so a document of 12,000 words has about 80 passages (about
  0.8 MB) and ten such documents about 8 MB per search page. That is an
  estimate, not a measurement: the real index cannot be reached now. So the
  read logs one line per search (number of ids, number of passages, bytes
  where the driver knows them, milliseconds; no id, no text), and the figure
  from the rehearsal on the real dossier goes into the docs. If this read
  takes more than a second there, the server-side alternative below is
  reopened; that is a new decision, not a silent switch.
- **Offsets come from the text, deterministically.**
  `passages.split_spans(text) -> list[tuple[int, int]]` gives the same windows
  as `passages.split`, as character offsets into the text. The invariant, and
  its test: for every span, `" ".join(text[s:e].split())` equals the passage
  `split` returns at that position. The fragment is `text[s:e]`, so it stays a
  quotation of the stored text.
- **The closest passage.** `console_passage.best(text, vectors, query_vector,
  query) -> dict | None`: cosine of each passage vector with the question's
  vector (`zeef.similarity.cosine`, as `hybrid.py` uses), the winning span,
  the query words found in it, and the reason. All of this, and the trimming
  and the segments below, is in the new `console_passage.py`;
  `console_search.py` (173 lines) only calls it.
- **The question is embedded once more.** `hybrid.hybrid_search` embeds the
  question and does not hand the vector out. Changing what it returns touches
  the module that decides the order, so the console embeds the question a
  second time with the same embedder (one local call). If that call fails,
  the results stay on the page with today's fragments and the same notice as
  for an unreachable index: the search itself succeeded, and a page without
  results would hide that. No code that decides the order of hits changes.
- **Which words count, and how they are found.** As `console_data.fragment`
  does it: the words of the question are what its `_WORD` pattern finds,
  matched case-insensitively at a word start (`\b` + the escaped word, so
  "vergunning" also marks "vergunningen"). Only words of four characters or
  more count (see the reasons).
- **A passage is trimmed for the page.** A passage is 200 words, too long for
  a result row. The page shows a window of the passage around its first
  marked word, or its opening when nothing is marked, with "…" where it was
  cut. The window is still a substring of the stored text.
- **Marking is data, not markup.** `best` returns the shown text as a list of
  segments, each a piece of the stored text and a flag "marked". The template
  writes each segment through Jinja's autoescape and wraps the marked ones in
  `<mark>`. No `|safe`, no `Markup`, no HTML built in Python: the stored text
  is document content, and a `<script>` in it must arrive as text.
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
  - `passages_of` raises `SearchUnavailable`, or embedding the question for
    the passages fails: every hit shows today's fragment and the page says the
    passages are unavailable. The results themselves are still shown: they
    were already fetched.
  - A document without passage vectors: as the count mismatch.
- **The score moves to a `title` attribute.** It is still reported per hit, as
  the console requirement "The corpus can be searched from the console" asks,
  and the fragment is still a quotation of the pseudonymised text; that
  requirement is not modified.

## Where the code goes

- `passages.py`: `split_spans`;
- `search_index.py`, `opensearch_index.py`: `passages_of`, body in new
  `passage_reads.py`;
- new `console_passage.py`: `best`, the word matching, the trimming, the
  segments;
- `console_search.py` (173 lines): the calls only; `templates/search.html`:
  the segments, the reason, the notice, the score in a `title`.

## Rejected

- **Offsets stored in the index** (the first version): a mapping change and a
  backfill for something that can be computed from the stored text.
- **The kNN inner hit as "the passage that ranked the document"**: production
  ranks on whole-document vectors, so there is no such passage.
- **A second, nested kNN query over the shown ids with `inner_hits`**, so that
  OpenSearch picks the closest passage and returns only its position. It would
  keep the vectors on the server and the payload small. Not chosen now: what a
  nested kNN returns as inner hits, and how it filters on ids, depends on the
  k-NN engine and the OpenSearch version, and production's cannot be checked
  while it is unreachable; it would need a second implementation of the same
  choice in `InMemoryIndex`; and its score is the engine's, where the `mget`
  lets one function (`best`) decide for both drivers. It is the first thing to
  reopen if the measured payload is too heavy.
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
