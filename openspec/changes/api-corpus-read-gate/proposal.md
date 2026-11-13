# api-corpus-read-gate

## Why

"Only readers see the corpus" is true of the console and not of the API. Issue
#442: a caller who is logged in and on no read list gets 200 on search, hybrid
search, `/ask`, the ranking export, a document's metadata and state, and a
grant's details. None of those routes calls `authorize_corpus_read`; the
console pages, the de-identified text, the corpus ZIP and the redacted PDF do.

Measured on the local demo (`tools/demo`, origin/main `1dabaab`, 2026-11-13) as
`gast`, a key on no list, against every one of the 55 routes the application
mounts. Beyond the seven routes of #442 the same caller also:

- read a dossier's topics (`GET /dossiers/{id}/topics`, 200);
- **recomputed** a dossier's topics (`POST /dossiers/{id}/topics`, 200) and
  **renamed** one (`PATCH /topics/{id}`, 200);
- **wrote a `detection_feedback` record** on a document's audit chain
  (`POST /documents/{id}/feedback`, 201, caller `gast`), and learned from 404
  against 201 which document ids exist;
- opened `/console/combinations` (200: every declared combination with the
  number of documents it reaches) and **declared one**, overwriting the reason
  of an existing declaration (`POST`, 303). These two console routes call no
  check at all.

The content is pseudonymised. It is still the corpus, and three of these are
writes.

## What changes

- Every route that returns corpus content or corpus metadata requires corpus
  read: 11 API routes and 2 console routes are newly gated; the 14 that are
  gated already keep their gate. The full inventory of 55 routes is in
  design.md.
- The check moves out of the route bodies into one reusable dependency, in a
  new module `read_gate.py`, declared on the route. `api.py` does not grow.
- A refusal comes before any lookup: a caller without corpus read gets 403 for
  a known and for an unknown id, and nothing is written.
- `GET /grants/{id}` admits a corpus reader or a grant issuer.
- A test walks the application's routes and fails when a route is not in the
  inventory, so a new route without a decision cannot be merged green.

## What does not change

- Where `WORDSWORTH_CORPUS_READ_LABELS` is empty the scope is off and every
  caller reads, as today. Without api-key auth nothing changes.
- A caller on the list gets the answers he got before.
- `/health`, `/metrics`, the login page and its assets, logout, the root
  redirect and the API schema stay as open as they are (design.md says why,
  per route).
- The write path: `POST /ingest`, `/reprocess` and `/datasets/pseudonymize`
  stay open to any logged-in caller. Whether ingest needs its own label is
  issue #431, and this change decides nothing there.
- Reveal, grant issue and revoke, roles, and delete keep their own gates.

## This is the deploy gate for sharing

`share-recipient-read` (#439) and `console-share` (#440) create the first
callers who are logged in and are not corpus readers. Neither is deployed, and
no non-reader gets a key or a login (M4, #418), before this change is in
production. Order and composition with #439 are in design.md.

## Out of scope

An ingest label (#431); the staleness check on `reveal.pdf` (#438); the actor
on grant revoke (#443); a thin client that can send a key (#445, see
design.md "Migration"); who may overwrite somebody else's declared
combination; a dossier scope on `/ask` and `/export/ranking.csv`.
