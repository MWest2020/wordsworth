# Tasks

`particle-names-rule` has merged; nothing blocks the build.

## 1. Count-only check
- [ ] `reprocess_counts.compare(before_text, after_text)` returns, per type,
      the distinct pseudonyms before, after, added and removed. Proved by:
      unit tests with texts where a type grows, shrinks, stays equal in total
      while one token is replaced (added 1, removed 1), and where a token
      occurs five times and counts once.
- [ ] `reprocess.one` logs one line per re-anonymised document with the
      document id and those numbers per type. Proved by: a test that
      re-anonymises a document with a detector that finds one more name the
      second time, and asserts the captured log holds the id and the four
      numbers per type.
- [ ] The check holds no value. Proved by: a test that runs it on a document
      with a detected name and asserts the captured logs and output contain
      neither the name, a pseudonym token, the surrounding text nor an offset.
- [ ] A skipped or failed document logs no count line and keeps its outcome.
      Proved by: a test with a document in a state reprocess skips and one
      whose anonymiser raises.

## 2. Docs (must change with the code)
- [ ] `docs/how-to/detection-lists.md`, section "Het bestaande corpus
      bijwerken": that a rule or gazetteer change does not move `lists_hash`,
      so `only_outdated` selects nothing and the ids are passed explicitly;
      how to list a dossier's ids; the count line and how to read it
      (distinct pseudonyms, added and removed); that it does not prove a name
      is gone. Proved by: `grep -n "document_ids"
      docs/how-to/detection-lists.md` finds the section, and the section names
      the check.

## 3. Check
- [ ] `openspec validate reanonymise-particle-name-documents --strict` passes.
- [ ] `uv run ruff check src/ tests/` and the full test suite pass; skipped database
      tests are listed in the report; `reprocess.py` stays under 200 lines.
      Proved by: the output in the PR.
- [ ] Local check: reprocess one seeded document whose text holds a gazetteer
      name with a particle. Proved by: the log line pasted in the PR.

## Not part of the build

- The run over the Gooise Meren dossier (operator, when production is
  reachable), and the update of the pilot report that follows from it.
