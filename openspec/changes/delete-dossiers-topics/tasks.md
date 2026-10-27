# Tasks

## 1. Code
- [ ] `delete_dossier` removes the dossier's `topics` rows before the dossier
      row, in the same transaction.
      Proved by: a test in `tests/test_delete_dossiers.py` with a dossier that
      has topics: the real run succeeds (no `ForeignKeyViolation`), no topic row
      of that dossier remains, and a topic of another dossier is untouched.
- [ ] `DossierDeletionReport` carries a `topics` count, in the API response of
      `DELETE /dossiers/{id}` and in the CLI output.
      Proved by: the same test asserts the count in the API body, and
      `tests/test_delete_cli.py` asserts it in the `--dossier` output.
- [ ] The dry run reports the topic count and removes nothing.
      Proved by: a CLI test with `--dry-run` on a dossier with topics: the count
      is printed, the topic rows still exist, and the later real run reports the
      same count.
- [ ] A dossier without topics reports `0` and behaves as before.
      Proved by: the existing empty-dossier and several-documents tests, with
      the count asserted as 0.
- [ ] A failure during the deletion leaves the topics in place.
      Proved by: a test with a failing index: the call fails, the topics and the
      dossier remain, a retry completes.

## 2. Docs
- [ ] `docs/how-to/deleting-documents.md`, section "Delete a dossier": say that
      the dossier's topics are removed with it and that the dry run and the
      report show their count.
      Proved by: the section names topics and the count; `grep -n topics
      docs/how-to/deleting-documents.md` finds it.
- [ ] `docs/reference/cli.md`, section `--dossier`: same, and the output field.
      Proved by: `grep -n topics docs/reference/cli.md` finds it under
      `--dossier`.

## 3. Check
- [ ] Run the real artefact against a dossier with topics (a private test
      database), not only the suite.
      Proved by: `wordsworth-delete --dossier <id> --dry-run` and then the real
      run on a dossier that previously failed, with exit code 0.
