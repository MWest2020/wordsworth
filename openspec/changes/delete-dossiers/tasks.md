# Tasks

## 1. Deleting a dossier
- [ ] `DELETE /dossiers/{id}` removes the memberships and the dossier row, and
      deletes each member document that belongs to no other dossier.
      Proved by: an API test with a dossier of several documents
      (`tests/test_delete_dossiers.py`) — each exclusive document has a
      `deleted` record and no content, the dossier no longer exists.
- [ ] A document that also belongs to another dossier loses only its membership.
      Proved by: a test with a shared document — its content, its other
      membership and a search scoped to the other dossier are unchanged.
- [ ] An empty dossier is removed and no document changes.
      Proved by: a test with an empty dossier.
- [ ] One `dossier-deleted` audit record per document touched, ids and counts
      only.
      Proved by: a test reads the records of an exclusive and a shared document
      and asserts the ids, the actor and that no name, value or token appears.
- [ ] The guard is the one document deletion uses.
      Proved by: a test with a refused caller — 403, the dossier and its
      memberships remain, no record is written; a beheerder and an issuer label
      are allowed.

## 2. The CLI
- [ ] `wordsworth-delete --dossier <id> [--dry-run]` in
      `wordsworth.delete_cli`.
      Proved by: `tests/test_delete_cli.py` drives `main`: `--dry-run` reports
      which documents would be deleted and which only released, changes
      nothing and writes no record; the real run then does exactly what was
      reported.

## 3. Docs (CI fails on code without docs)
- [ ] `docs/how-to/deleting-documents.md`: close the open question under "What
      is not here", add "Delete a dossier" (shared documents, the dossier row,
      `dossier-deleted`, who may). Proved by: docs review in the PR.
- [ ] `docs/reference/cli.md`: `--dossier` under `wordsworth-delete`.
      Proved by: docs review in the PR.

## 4. The real artefact
- [ ] Dry-run, then delete, the 10 empty dossiers on the deployment, and call
      `DELETE /dossiers/{id}` as a caller who is not beheerder (refused).
      Operator step after the deploy; the builder has no access to the live
      deployment.

Only check off a task whose named test exists and passes.
