# Tasks

## 1. Passage spans and the read
- [ ] `passages.split_spans(text)` returns the windows of `passages.split` as
      character offsets. Proved by: a test over an empty text, a text shorter
      than one window, one with a tail the stride steps over, and one with
      newlines and repeated spaces, asserting for every span that
      `" ".join(text[s:e].split())` equals the passage `split` returns.
- [ ] `SearchIndex.passages_of(ids)` on the protocol, `InMemoryIndex` and
      `OpenSearchIndex`; an id without passages is absent from the answer or
      has an empty list; a transport failure raises `SearchUnavailable`; more
      than ten ids is a `ValueError` on both drivers. Proved by: unit tests on
      `InMemoryIndex`, and an OpenSearch integration test next to
      `tests/test_opensearch_index.py` that the CI log shows as passed, not
      skipped.
- [ ] The read logs one line per call with the number of ids, the number of
      passages and the milliseconds, and no id or text. Proved by: a test on
      the captured log.

## 2. The closest passage
- [ ] `console_passage.best` returns the span of the passage with the highest
      cosine to the question's vector. Proved by: a test with a document whose
      second passage holds the answer: that passage's span is returned.
- [ ] The reason and the marking: "op woorden en betekenis" with the query
      words of four characters or more marked; "op betekenis" with nothing
      marked. Proved by: one test per reason, the second with a passage that
      shares no word with the question.
- [ ] Matching is case-insensitive and at a word start, as
      `console_data.fragment`. Proved by: a test where "Vergunning" in the
      question marks "vergunningen" in the passage, "de" marks nothing, and a
      word that only occurs inside another word ("gunning") marks nothing.
- [ ] A long passage is shown as a window around its first marked word, or its
      opening when nothing is marked; the shown text is a substring of the
      stored text. Proved by: a test with a 200-word passage whose marked word
      is near the end.
- [ ] `best` returns segments (text, marked), and `console_passage.py` builds
      no HTML. Proved by: a test on the returned structure, and `grep -n
      "Markup\|<mark" src/wordsworth/console_passage.py` finds nothing.
- [ ] A count mismatch gives no passage. Proved by: a test where the number of
      vectors differs from the number of windows: `best` returns `None`.

## 3. Console
- [ ] A result shows the closest passage with its reason; the passage is a
      substring of the stored pseudonymised text. Proved by: a console test
      asserting the shown passage occurs literally in the stored text.
- [ ] A count mismatch, and a document without passage vectors, show today's
      fragment without a reason. Proved by: a console test for each.
- [ ] An index that fails on `passages_of` leaves the results on the page with
      today's fragments, and the page says the passages are unavailable.
      Proved by: a console test with an index that raises `SearchUnavailable`
      on `passages_of` only.
- [ ] A failing second embedding of the question does the same. Proved by: a
      console test with an embedder that answers the first call and raises on
      the second: results shown, today's fragments, the notice.
- [ ] Stored text arrives as text. Proved by: a console test with a document
      whose stored text holds `<script>alert(1)</script>` next to a query
      word: the response contains `&lt;script&gt;` and no `<script>alert`, the
      query word is inside `<mark>`, and `grep -n "safe"
      src/wordsworth/templates/search.html` finds no `|safe` on the passage.
- [ ] With `size=25`, the first ten hits show a passage and the others today's
      fragment; `passages_of` was called once with ten ids. Proved by: a
      console test with a recording index.
- [ ] A keyword search (no embedder) shows today's fragment with the reason
      "op woorden" and does not call `passages_of`. Proved by: a console test.
- [ ] The order of hits is unchanged. Proved by: a test that the list of
      document ids on the page equals the list the ranking returned, for the
      same index and question, with and without passage vectors.
- [ ] The score is in a `title` attribute and no longer in its own column.
      Proved by: a console test on the HTML.

## 4. Docs
- [ ] `docs/how-to/console.md`: what a result shows, the three reasons, the
      four-character rule and how words are matched, that only the first ten
      hits get a passage, when today's fragment is shown instead, and the log
      line with the payload estimate, marked as an estimate until the
      rehearsal measures it. Proved by:
      `grep -n "op betekenis" docs/how-to/console.md` finds it.
- [ ] New `docs/explanation/why-a-result-matched.md`: closest passage against
      ranking passage, why nothing is stored, the limits of design.md. Proved
      by: the file exists with front matter (`status`, `last_reviewed`) and is
      linked from `docs/index.md`.

## 5. Check
- [ ] `openspec validate search-matching-passage --strict` passes.
- [ ] `uv run ruff check src/ tests/` is clean and the full suite passes; the
      new modules are under 200 lines and `git diff --stat` shows no change to
      the index mapping or to `hybrid.py`'s ordering. Proved by: the output in
      the PR, with the skipped tests listed.
