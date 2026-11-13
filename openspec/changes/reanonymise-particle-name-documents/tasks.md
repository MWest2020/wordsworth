# Tasks

`particle-names-rule` has merged; nothing blocks the build.

## 1. Count-only check
- [x] `reprocess_counts.compare(before_text, after_text)` returns, per type,
      the distinct pseudonyms before, after, added and removed. Proved by:
      unit tests with texts where a type grows, shrinks, stays equal in total
      while one token is replaced (added 1, removed 1), and where a token
      occurs five times and counts once.
- [x] `reprocess.one` logs one line per re-anonymised document with the
      document id and those numbers per type, after the commit. Proved by: a
      test that re-anonymises a document with a detector that finds one more
      name the second time, and asserts the captured log holds the id and the
      four numbers per type; and a test with a session whose `commit` raises:
      no count line was logged.
- [x] `POST /reprocess` returns the same numbers per document in
      `ReprocessResponse.entity_counts`, and `reprocess.run` still returns
      `(counts, problems)`. Proved by: an API test on the answer for two
      documents, one re-anonymised and one skipped (absent from
      `entity_counts`), asserting the answer holds no token and no value.
- [x] The counting lives in `reprocess_counts.py`. Proved by: `wc -l
      src/wordsworth/reprocess.py` is under 200 and `grep -n "tokens_in"
      src/wordsworth/reprocess.py` finds nothing.
- [x] The check holds no value. Proved by: a test that runs it on a document
      with a detected name and asserts the captured logs and output contain
      neither the name, a pseudonym token, the surrounding text nor an offset.
- [x] A skipped or failed document logs no count line and keeps its outcome.
      Proved by: a test with a document in a state reprocess skips and one
      whose anonymiser raises.

## 2. Docs (must change with the code)
- [x] `docs/how-to/detection-lists.md`, section "Het bestaande corpus
      bijwerken": that a rule or gazetteer change does not move `lists_hash`,
      so `only_outdated` selects nothing and the ids are passed explicitly;
      how to list a dossier's ids; the count line and how to read it
      (distinct pseudonyms, added and removed); where to read it (the
      `entity_counts` of the answer, which the Job prints, and the service's
      log line); that it does not prove a name is gone; that after a change of
      the domain key or of the profile every token is a new one, so added and
      removed both equal the whole count and say nothing about detection; and
      that in irreversible mode there are no pseudonym tokens, so the check
      finds nothing (and `/reprocess` is not offered there). Proved by: `grep
      -n "document_ids\|entity_counts" docs/how-to/detection-lists.md` finds
      the section, and the section names the check and both notes.

## 3. Check
- [x] `openspec validate reanonymise-particle-name-documents --strict` passes.
- [x] `uv run ruff check src/ tests/` and the full test suite pass; skipped database
      tests are listed in the report; `reprocess.py` stays under 200 lines.
      Proved by: the output in the PR.
- [x] Local check: reprocess one seeded document whose text holds a gazetteer
      name with a particle. Proved by: the log line pasted in the PR.

## Not part of the build

- The run over the Gooise Meren dossier (operator, when production is
  reachable), and the update of the pilot report that follows from it.
