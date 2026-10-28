# console-share

## Why

Mark, 2026-10-28: the key user wants to *"share with layered
anonymisation"*. Today the console can't issue a grant (document page: "De
console mag er zelf geen uitgeven"), so sharing means the API or the CLI, and
grants are per document: sharing a dossier took 405 grants. The review (docs/explanation/review-key-user-2026-10-28.md)
puts a share flow in the console, behind the same issuer gate.

## What changes

- A "Delen" action on a document, a topic and a dossier: choose a recipient
  (a known caller label or email), a level (PPL 0–3) or a role, and an expiry.
- The console issues the grants through the same code and gate as `POST
  /grants`: only `beheerder` or an issuer label may share. For a topic or a
  dossier it issues one grant per live document and reports how many.
- The result page lists what the recipient can open: the redacted PDF links,
  and that reveals need the recipient's own login.
- Revoking a share revokes its grants in one step.

## Out of scope

Sending mail or messages to the recipient; new grant semantics (a grant stays
per document or global); external recipients without a login.
