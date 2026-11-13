# Tasks

Built after `share-recipient-read` is on main.

## 1. Sharing
- [ ] `grants.share_id`: nullable column in `models.py` and `db._COLUMNS`.
      Proved by: a test that runs `init_schema` on a database whose `grants`
      table lacks it, and a test that a grant issued through `POST /grants`
      has it NULL.
- [ ] `shares.share(session, store, key_audit, scope, recipient, *, ppl|role,
      expires_at, actor, index)` issues one grant per live document through
      `grants.issue_grant`, under one share id, in one transaction. Proved by:
      one test per scope (document, topic with `InMemoryIndex`, dossier)
      asserting the grant rows, their `share_id`, their domain, and one
      `grant_issued` event per grant.
- [ ] A dossier holding a deleted document and a superseded copy issues no
      grant for either. Proved by: a test. A dossier of more than 200 live
      documents issues one grant for each. Proved by: a test with 201.
- [ ] A topic is read from the index; a stale index entry for a deleted
      document issues nothing. Proved by: a test.
- [ ] Index down while sharing a topic: nothing issued. Proved by: a test with
      an index whose `documents_in` raises `SearchUnavailable`: the call
      raises it, zero grant rows, zero audit events; and a test that sharing a
      document and a dossier works with that same index.
- [ ] All or nothing. Proved by: a test in which `issue_grant` fails on the
      third document and, after rollback, no grant row and no audit event of
      that share exists.
- [ ] Every refusal before a write: empty recipient, both and neither of
      `ppl`/`role`, `ppl` 4, unknown role, role `beheerder`, expiry missing,
      naive, in the past, unknown document/topic/dossier, a scope without a
      live document. Proved by: one test per case asserting zero rows and zero
      events.
- [ ] Defaults PPL 0 and 30 days. Proved by: a console test posting the form
      with only a recipient.
- [ ] `shares.revoke(session, store, key_audit, share_id, actor)` revokes every
      active grant of the share, one `grant_revoked` event each, with the
      caller as actor. Proved by: a test; a test that a second revoke returns 0
      and writes no event; a test that a grant of another share and a grant
      without a share stay active; a test that an unknown share id is 404.
- [ ] Deleting a shared document needs no change. Proved by: a test that
      deletes one document of a share and then revokes the share.

## 2. The gate
- [ ] All five routes call `_guard_grant_admin`, which is
      `authorize_grant_issue`. Proved by: one parametrised test over the five
      routes as a logged-in caller who is not an issuer label, including one
      who is on the corpus-read list and one who holds the beheerder role: 403
      each, zero grant rows, zero audit events.
- [ ] `_may_issue` and `_guard_grant_admin` are one decision. Proved by: a
      test that "Delen" is absent from the document, topic and dossier page
      for a corpus reader who is not an issuer, and present for an issuer; and
      the existing grant-admin tests unchanged and green.
- [ ] An empty issuer list refuses everybody. Proved by: a test.

## 3. Console
- [ ] The form, the list, the result page, revoke. Proved by: console tests
      per route in `tests/test_console_share.py`.
- [ ] The result page links the document page for every document and the
      redacted PDF only where a box map exists. Proved by: a test with one
      document with and one without a `BoxMap` row.
- [ ] The recipient can open what the result page lists. Proved by: a test
      that shares a dossier, collects the links from the result page and
      requests each **as the recipient** (not on the corpus-read list): 200;
      and after revoke: 403. This test fails without `share-recipient-read`.
- [ ] Index down: 503 and the message, nothing issued. Proved by: a console
      test.
- [ ] No value in a message. Proved by: a test that the form, the result page,
      the list and every refusal contain none of the seeded clear values of
      the shared documents.
- [ ] No file over 200 lines is new, and `grants.py` is unchanged. Proved by:
      `wc -l` and the diff in the PR.

## 4. Docs
- [ ] `docs/how-to/grants.md`: sharing from the console, who may (issuer
      labels), defaults, that a share is a snapshot, revoking, the index for a
      topic. Front matter `status`, `last_reviewed`.

## 5. Local check
- [ ] In the harness (`tools/demo/serve_local.py --reset`), in a browser
      session as `mark`: share the demo dossier with `gast` at PPL 1 (28
      grants: the two deleted letters and the superseded scan get none). As
      `gast`: open one link from the result page (200), open
      `/console/gedeeld` (28 rows), `/console/share?dossier=…` (403). As
      `mark`: revoke. As `gast`: the same link (403). Proved by: the status
      codes and the two counts pasted in the PR.
- [ ] `/security-review` on the diff, clean or every finding answered in the
      PR.
