# Tasks

## 1. Authorisation
- [ ] Add a check that allows only role `beheerder` or an issuer label, used by
      both endpoints and the CLI.
      Proved by: `tests/test_delete_documents.py` — a beheerder and an issuer
      label are allowed; any other caller gets 403 and nothing is removed; no
      `deleted` record exists after a refusal.

## 2. Deleting a document
- [ ] Remove the object, text, pseudonyms, mappings, index entries and grants of
      one document, keep the `documents` row.
      Proved by: a test that deletes an indexed document and then finds none of
      the six in their stores, while the row and its earlier audit records remain.
- [ ] Write one `deleted` audit record in the same transaction as the removal,
      holding ids and counts only.
      Proved by: a test that reads the record and asserts no filename, text,
      token or value appears in it, and that the hash chain still verifies.
- [ ] Add state `deleted` to the state machine (terminal, from every state).
      Proved by: the `document-lifecycle` tests: no transition leaves `deleted`.
- [ ] A removal that fails writes no `deleted` record and leaves the state
      unchanged; a rerun finishes.
      Proved by: a test with a failing index driver, then a healthy rerun.
- [ ] `DELETE /documents/{id}`; an unknown id is 404.
      Proved by: API tests.

## 3. Deleting a dossier
- [ ] `DELETE /dossiers/{id}` deletes each document of the dossier as in 2.
      Proved by: an API test with a dossier of several documents.
      Blocked on the open questions about shared documents and the dossier row;
      do not guess them.

## 4. The CLI
- [ ] A CLI for a document or a dossier, with `--dry-run`, registered in
      `pyproject.toml` (name: see open questions).
      Proved by: a test that `--dry-run` prints the counts, removes nothing and
      writes no audit record, and that the same run without it removes them.

## 5. Docs (CI fails on code without docs)
- [ ] `docs/reference/cli.md`: the new command, `--dry-run`, and amend the
      sentence "A retired copy is not deleted" so it does not read as "nothing
      is deleted". Proved by: docs review in the PR.
- [ ] `docs/reference/architecture.md`: the audit/state section, for state
      `deleted` and the row that stays. Proved by: docs review.
- [ ] A how-to for deleting (who may, what goes, what stays, dry run), and
      `docs/how-to/roles.md` or `grants.md` for who may. Proved by: docs review.

## 6. The real artefact
- [ ] Run the CLI with `--dry-run` on the 12-document pilot dossier and compare
      the counts with what the stores hold; then delete it and check each store
      and the audit trail from the API as a caller who is not beheerder (refused).
