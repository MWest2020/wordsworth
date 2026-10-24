# Tasks

## 1. Authorisation
- [x] Add a check that allows only role `beheerder` or an issuer label, used by
      both endpoints and the CLI.
      Proved by: `tests/test_delete_documents.py` — a beheerder and an issuer
      label are allowed; any other caller gets 403 and nothing is removed; no
      `deleted` record exists after a refusal.
      Note: "how a caller is known to hold `beheerder`" was an open question.
      Resolved here as: the caller is the recipient of an active, unexpired
      grant naming the role (`grants.caller_holds_role`) — the one place an
      identity is already tied to a role name in this codebase (see
      `design.md` note added below and `docs/how-to/deleting-documents.md`).
      Not a general identity-to-role mapping; flag for Mark if a different
      answer was intended.

## 2. Deleting a document
- [x] Remove the object, text, pseudonyms, mappings, index entries and grants of
      one document, keep the `documents` row.
      Proved by: a test that deletes an indexed document and then finds none of
      the six in their stores, while the row and its earlier audit records remain.
      (`tests/test_delete_documents.py::test_deletion_removes_the_six_kinds_and_keeps_the_row_and_the_trail`)
- [x] Write one `deleted` audit record in the same transaction as the removal,
      holding ids and counts only.
      Proved by: `test_deleted_audit_record_carries_ids_and_counts_only`
      reads the record and asserts no filename, text, token or value appears in
      it.
- [x] After a deletion the trail is kept: the earlier audit records are
      unchanged and the chain still verifies (spec scenario "The trail is
      kept"; reviewer finding on #235).
      Proved by: `test_deleted_audit_record_carries_ids_and_counts_only`, or a
      new test next to it, calls `audit.verify_chain(session)` after a deletion
      and asserts that it passes and that the earlier records are still there
      and unchanged.
- [x] Add state `deleted` to the state machine (terminal, from every state).
      Proved by: the `document-lifecycle` tests: no transition leaves `deleted`.
      (`tests/test_states.py::test_every_state_can_be_deleted_and_deleted_is_final`)
- [x] A removal that fails writes no `deleted` record and leaves the state
      unchanged; a rerun finishes.
      Proved by: a test with a failing index driver, then a healthy rerun.
- [x] `DELETE /documents/{id}`; an unknown id is 404.
      Proved by: API tests.

## 3. Deleting a dossier
- [ ] `DELETE /dossiers/{id}` deletes each document of the dossier as in 2.
      Proved by: an API test with a dossier of several documents.
      Blocked on the open questions about shared documents and the dossier row;
      do not guess them.
      **Not implemented in this change** — still blocked on those two open
      questions (a document shared with another dossier; whether the dossier
      row itself goes). Needs an explicit decision before this can proceed.

## 4. The CLI
- [x] A CLI for a document, with `--dry-run`, as module
      `wordsworth.delete_cli` with a `main`, registered in `pyproject.toml`
      as `wordsworth-delete` (script name was an open question; chosen to
      match the `wordsworth-<verb>` convention of the other CLIs).
      Proved by: `tests/test_delete_cli.py` drives `wordsworth.delete_cli.main`
      itself: with `--dry-run` it prints the counts, removes nothing and writes
      no audit record; the same run without `--dry-run` removes the documents.
      A bare import or attribute reference of `main` does not count as proof.
      **Dossier support is not implemented** (see §3) — the CLI takes only
      document ids.

Only check off a task whose named test exists and passes.

## 5. Docs (CI fails on code without docs)
- [x] `docs/reference/cli.md`: the new command, `--dry-run`, and amend the
      sentence "A retired copy is not deleted" so it does not read as "nothing
      is deleted". Proved by: docs review in the PR.
- [x] `docs/reference/architecture.md`: the audit/state section, for state
      `deleted` and the row that stays. Proved by: docs review.
- [x] A how-to for deleting (who may, what goes, what stays, dry run), and
      `docs/how-to/roles.md` or `grants.md` for who may. Proved by: docs review.
      (`docs/how-to/deleting-documents.md`, cross-linked from both.)

## 6. The real artefact
- [ ] Run the CLI with `--dry-run` on the 12-document pilot dossier and compare
      the counts with what the stores hold; then delete it and check each store
      and the audit trail from the API as a caller who is not beheerder (refused).
      **Not done in this change** — the builder agent has no access to the
      deployed pilot dossier, S3/SeaweedFS, OpenSearch or the live API. This is
      an operator step to run against the real deployment before closing the
      change.
