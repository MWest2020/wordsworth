# Tasks

## 1. One rule
- [ ] A helper in `src/wordsworth/console_data.py` that says whether a document
      is hidden by default (state `deleted`, or superseded) and a query
      condition for the same. Proved by: `tests/test_console.py`, a unit test of
      the helper over a live, a deleted and a superseded document.

## 2. The three pages
- [ ] `/console` (`src/wordsworth/console.py`): hides deleted and superseded
      documents by default, shows them with the toggle, and the total follows the
      same rule. Proved by: a test in `tests/test_console.py` with one live, one
      deleted and one superseded document, without and with the toggle.
- [ ] `/console/search` (`src/wordsworth/console_search.py`): hits for hidden
      documents are left out by default and shown with the toggle. Proved by: a
      test in `tests/test_console.py` or `tests/test_console_vraag.py` with an
      index entry for a deleted document.
- [ ] `/console/topics` (`src/wordsworth/console_topics.py`): hidden documents
      are not counted or listed by default, and are with the toggle. Proved by:
      a test in `tests/test_console_topics.py`.
- [ ] Each page says when it is hiding documents and offers the toggle. Proved
      by: the same three tests assert the notice is present when something is
      hidden and absent when nothing is.
- [ ] `/console/documents/{id}` still opens a deleted document. Proved by: an
      existing or new assertion in `tests/test_console.py`.

## 3. Docs (must change with the code)
- [ ] `docs/how-to/console.md`, "What the pages show" and "Searching": the
      default, the toggle, and that superseded copies are hidden the same way.
      Proved by: the sections name the default and the toggle.
- [ ] `docs/how-to/topics.md`: the topics page hides deleted and superseded
      documents by default. Proved by: the page says so.
- [ ] `openspec validate console-hide-deleted --strict` passes.
