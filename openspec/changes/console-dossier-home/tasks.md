# Tasks

## 0. Precondition
- [ ] `console-hide-deleted` is built and merged before this change is built.
      Proved by: its shared helper exists in `console_data.py`; this change
      imports it and `grep` finds no second deleted/superseded filter in
      `console_dossier.py`.

## 1. Home and dossier page
- [ ] The new routes live in `src/wordsworth/console_dossier.py`, registered
      from the app; `console.py` and `dossiers.py` do not grow. Proved by: a
      check that `wc -l` of `console.py` and `dossiers.py` is no higher than
      before the change and `console_dossier.py` is at most 200 lines.
- [ ] `/console` lists dossiers (name, live documents, topics) and redirects to
      the dossier page when there is exactly one. Proved by: tests in
      `tests/test_console.py` for zero, one and two dossiers.
- [ ] `/console/dossier?dossier=<name>` shows a question box (GET to
      `/console/search?dossier=`), the dossier's topics with counts and a
      search-within-topic link, and its live documents. Proved by: a test with a
      dossier holding a live, a deleted and a superseded document and one topic:
      only the live document is listed, the topic link carries `topic=`.
- [ ] A dossier name with a slash and one with a space resolve to their page.
      Proved by: a test with names `a/b` and `a b` (URL-encoded in the query),
      each answering 200 with its own documents; the home page links to them.
- [ ] An unknown dossier name answers 404 with the list of dossiers, not an
      empty page. Proved by: a test, including an unknown name containing a
      slash.
- [ ] "All documents" keeps the previous list reachable. Proved by: a test that
      the link resolves.

## 2. Docs
- [ ] `docs/how-to/console.md`: the console starts on a dossier; what the page
      shows; the `?dossier=` address; where the full list went. Proved by: the
      docs check in CI passes with the code change.
