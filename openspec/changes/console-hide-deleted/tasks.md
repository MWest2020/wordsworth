# Tasks

## 1. One rule
- [ ] A helper in `src/wordsworth/console_data.py` that says whether a document
      is hidden by default (state `deleted`, or superseded) and a query
      condition for the same. Proved by: `tests/test_console.py`, a unit test of
      the helper over a live, a deleted and a superseded document.

## 2. The list (the whole build)
- [ ] `/console` (`src/wordsworth/console.py`): hides deleted and superseded
      documents by default, shows them with an explicit toggle, and the total
      follows the same rule. Proved by: a test in `tests/test_console.py` with
      one live, one deleted and one superseded document, without and with the
      toggle.
- [ ] The list says when it is hiding documents, with one total, and offers the
      toggle. Proved by: the same test asserts the notice is present when
      something is hidden and absent when nothing is.
- [ ] `/console/documents/{id}` still opens a deleted document. Proved by: an
      existing or new assertion in `tests/test_console.py`.

## 3. Search guard
- [ ] `/console/search` (`src/wordsworth/console_search.py`): no toggle; a hit
      for a hidden document is left out. Proved by: a test in
      `tests/test_console.py` or `tests/test_console_vraag.py` that builds a
      stale index entry for a deleted document by hand and shows the guard
      drops it. The test says in its name and docstring that it builds the
      stale entry by hand; it does not claim that deletion leaves hits behind.

## 4. Topics
- [ ] Nothing is built. Proved by: `src/wordsworth/console_topics.py` is not in
      the diff.

## 5. Docs (must change with the code)
- [ ] `docs/how-to/console.md`, "What the pages show": the list hides deleted
      and superseded documents by default, the toggle, the one-total notice.
      Proved by: the section names the default and the toggle.
- [ ] `docs/how-to/console.md`, "Searching": a hit for a deleted or superseded
      document does not appear; there is no toggle, because deletion removes
      the index entry. Proved by: the section says so.
- [ ] `docs/how-to/topics.md` is not changed: the page keeps showing the
      persisted `document_count`. Proved by: it is not in the diff.
- [ ] `openspec validate console-hide-deleted --strict` passes.
