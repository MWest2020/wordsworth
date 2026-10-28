# Tasks

## 1. Home and dossier page
- [ ] `/console` lists dossiers (name, live documents, topics) and redirects to
      the dossier page when there is exactly one. Proved by: tests in
      `tests/test_console.py` for zero, one and two dossiers.
- [ ] `/console/dossiers/{name}` shows a question box (GET to
      `/console/search?dossier=`), the dossier's topics with counts and a
      search-within-topic link, and its live documents. Proved by: a test with a
      dossier holding a live, a deleted and a superseded document and one topic:
      only the live document is listed, the topic link carries `topic=`.
- [ ] An unknown dossier name answers 404 with the list of dossiers, not an
      empty page. Proved by: a test.
- [ ] "All documents" keeps the previous list reachable. Proved by: a test that
      the link resolves.

## 2. Docs
- [ ] `docs/how-to/console.md`: the console starts on a dossier; what the page
      shows; where the full list went.
