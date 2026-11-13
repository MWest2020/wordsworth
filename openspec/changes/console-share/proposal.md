# console-share

## Why

Mark, 2026-10-28: the key user wants to *"share with layered
anonymisation"*. Today the console can't issue a grant (document page: "De
console mag er zelf geen uitgeven"), so sharing means the API or the CLI, and
grants are per document: sharing a dossier took 405 grants. The review (docs/explanation/review-key-user-2026-10-28.md)
puts a share flow in the console, behind the same issuer gate.

## What changes

- A "Delen" action on a document, a topic and a dossier: choose a recipient
  (the name he logs in under, matched exactly), a level (PPL 0–3) or a role,
  and an expiry.
- The console issues the grants through the same function and the same gate as
  `POST /grants`. The gate is exactly `auth.authorize_grant_issue`: the issuer
  labels, and nobody else. For a topic or a dossier it issues one grant per
  live document and reports how many.
- A share is the set of grants one "Delen" issued, held together by a
  `share_id` on the grant rows. It is a snapshot: a document that joins the
  dossier or topic later is not shared.
- The result page lists what the recipient can open: per document the console
  page and, where a box map exists, the redacted PDF; and it says that reveals
  need the recipient's own login.
- Revoking a share revokes its grants in one step. A page lists the shares so
  a share can be found again.

## Depends on

`share-recipient-read`. Without it every link on the result page answers 403
for the recipient: reading is decided by the corpus-read list, not by grants,
and a grant at PPL 0 carries no types. This change is built after that one is
on main, and one of its tests opens a result link as the recipient.

## Amended 2026-11-13, after checking the code

- "Only `beheerder` or an issuer label may share" contradicted "the same gate
  as `POST /grants`": that gate is the issuer labels only
  (`auth.authorize_grant_issue`, called by `_guard_grant_admin`,
  `api.py:449`). `beheerder` is in the delete gate (`authorize_delete`), not in
  the grant gate. Decision: issue #417 (M3, `waiting-on-mark`), on its default:
  issuer labels only; "or beheerder" is gone from proposal, design, tasks and
  spec. If Mark answers otherwise, that is a change to the grant gate itself,
  for the API as well, and not a console exception.
- The recipient could not open the links (issue #416, M2): now the dependency
  above.
- Storage of the share id, the module the code lands in, and what sharing a
  topic does when the index is down were not stated; design.md states them.

## Out of scope

Sending mail or messages to the recipient; new grant semantics (a grant stays
per document or global, and a share issues only per-document grants); external
recipients without a login; what a recipient may read (`share-recipient-read`).
