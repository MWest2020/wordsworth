# Tasks

Build only after `detect-dutch-particle-names` has merged.

## 1. Count-only check
- [ ] Log per document the entity counts per type before and after
      re-anonymisation in the reprocess path. Proved by: a test that
      re-anonymises a document and asserts the log holds both counts per type.
- [ ] The check holds no value. Proved by: a test that runs the check on a
      document with a detected name and asserts the captured logs and output
      contain neither the name, the surrounding text nor an offset.

## 2. Docs (must change with the code)
- [ ] `docs/how-to/detection-lists.md`, section "Het bestaande corpus
      bijwerken": describe re-running after a detection change and the
      count-only check. Proved by: the section exists and names the check.

## 3. Check
- [ ] `openspec validate reanonymise-particle-name-documents --strict` passes.
- [ ] `uvx ruff check src/ tests/` and the full test suite pass; skipped database
      tests are listed in the report.
