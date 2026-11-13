# Tasks

## 0. Precondition
- [x] `console-hide-deleted` is built and merged before this change is built.
      Proved by: its shared helper exists in `console_data.py`; this change
      imports it and `grep` finds no second deleted/superseded filter in
      `console_dossier.py`.
      Done: `console_dossier.choices` uses `console_data.latest_state_subquery`
      and `hidden_condition`; the dossier page's documents come from
      `console_list.documents`, the list's own query. `grep -nE
      'DELETED|== *"deleted"|superseded_by *(\.is|==|!=)|is_hidden'
      src/wordsworth/console_dossier.py` finds nothing.

## 1. Home and dossier page
- [x] The new routes live in `src/wordsworth/console_dossier.py`, registered
      from the app; `console.py` and `dossiers.py` do not grow. Proved by: a
      check that `wc -l` of `console.py` and `dossiers.py` is no higher than
      before the change and `console_dossier.py` is at most 200 lines.
      Done: console.py 267 → 232, dossiers.py 216 → 216, console_dossier.py
      134, console_list.py 95 (the old list, moved). Proved by
      `test_the_routes_live_in_their_own_module_under_the_limit`.
- [x] `/console` lists dossiers (name, live documents, topics) and redirects to
      the dossier page when there is exactly one. Proved by: tests in
      `tests/test_console.py` for zero, one and two dossiers.
      Done in `tests/test_console_dossier.py` instead (test_console.py is 518
      lines): `test_without_dossiers_…`, `test_one_dossier_opens_directly`,
      `test_two_dossiers_show_the_picker_…` (live count excludes a deleted one).
- [x] `/console/dossier?dossier=<name>` shows a question box (GET to
      `/console/search?dossier=`), the dossier's topics with counts and a
      search-within-topic link, and its live documents. Proved by: a test with a
      dossier holding a live, a deleted and a superseded document and one topic:
      only the live document is listed, the topic link carries `topic=`.
      Done: `test_the_dossier_page_shows_question_box_topics_and_live_documents_only`.
      Extra (review: topics cover under half the dossier): the page says
      "x van y documenten vallen in een onderwerp";
      `test_the_page_says_how_much_of_the_dossier_the_topics_cover`,
      `test_without_topics_the_page_says_so`; topics counting more than the
      live documents say they are stale and link the topics page
      (`test_topics_counting_more_than_the_live_documents_say_they_are_stale`).
- [x] A dossier name with a slash and one with a space resolve to their page.
      Proved by: a test with names `a/b` and `a b` (URL-encoded in the query),
      each answering 200 with its own documents; the home page links to them.
      Done: `test_names_with_a_slash_and_a_space_resolve_to_their_own_page`;
      `&`, `#`, `%` and unicode in `test_console_dossier_edges.py`. A comma:
      `dossiers.resolve` tries the whole scope as one name before splitting
      (`test_a_dossier_with_a_comma_searches_itself_not_its_parts`).
- [x] An unknown dossier name answers 404 with the list of dossiers, not an
      empty page. Proved by: a test, including an unknown name containing a
      slash.
      Done: `test_an_unknown_dossier_answers_404_with_the_list`. No name at
      all answers 303 to `/console`
      (`test_no_dossier_named_goes_back_to_the_home_page`).
- [x] "All documents" keeps the previous list reachable. Proved by: a test that
      the link resolves.
      Done: `/console/documents`; `test_all_documents_keeps_the_full_list_reachable`;
      the existing list tests now request that path.

## 2. Docs
- [x] `docs/how-to/console.md`: the console starts on a dossier; what the page
      shows; the `?dossier=` address; where the full list went. Proved by: the
      docs check in CI passes with the code change.
      Done: `docs/how-to/console.md`, "What the pages show".
