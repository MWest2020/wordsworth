# share-recipient-read

## Why

A share gives its recipient nothing to open. Reading a document's redacted PDF
and its console page is decided by the static list
`WORDSWORTH_CORPUS_READ_LABELS` (`auth.authorize_corpus_read`), not by grants,
and a grant at PPL 0 expands to no types at all (`types_for_ppl(0) == set()`).
`console-share` as proposed therefore produces links its recipient gets a 403
on.

Checked on the local demo (`tools/demo`, origin/main `8bbbcec`, 2026-11-13):
`mark` issued a document-scoped grant at PPL 0 to `gast`; `gast` then got 403
on `GET /documents/{id}/redacted.pdf` and on `/console/documents/{id}`, and
403 "grant not applicable" on `POST /documents/{id}/reveal.pdf`.

Decision: issue #416 (M2, `waiting-on-mark`). This proposal is written on its
default, "yes, as its own change `share-recipient-read`: that document only, no
search, no list". If Mark answers otherwise, this change is withdrawn and
`console-share` loses its result links.

## What changes

- The recipient of an active, unexpired, document-scoped grant may open the
  redacted PDF and the console page of exactly that document, without being on
  the corpus-read list.
- A page "Gedeeld met mij" (`/console/gedeeld`) lists the documents shared with
  the caller, and only those.
- A caller admitted by a share alone does not see the document's original
  filename: he sees "document" and the first eight characters of its content
  hash. Filenames of Woo files often hold names, and the filename is not
  pseudonymised. A reader on the list sees filenames as today.
- The 403 page links that page, so a recipient who logs in and lands on a
  refusal has somewhere to go.
- The decision is one function, `auth.authorize_document_read`, next to
  `authorize_corpus_read`. Two places call it: the redacted-PDF route and the
  console document page.

## What does not change

- Console search (`/console/search`), the console's document list, dossier
  pages, topics and feedback overview, the export ZIP and
  `GET /documents/{id}/anonymized` stay behind the corpus-read list. A
  recipient gets 403 there as before.
- This is a statement about the console and those two API routes, not about
  the API as a whole: `GET /search`, `/hybrid`, `/ask` and several other
  routes call no corpus-read check today, for any logged-in caller (#442; see
  design.md, "Found and not changed"). This change neither opens nor closes
  them.
- A grant without a document scope (`document_id IS NULL`) is not a share and
  opens nothing here, whatever the deployment allows for reveals.
- Revealing: `POST /documents/{id}/reveal` and `/reveal.pdf` are decided by the
  grant alone today and stay that way. Nothing is added to them.
- A caller on the corpus-read list sees what he saw before.

## Depends on

- **#442 is a deploy gate.** No caller who is not a corpus reader gets a key or
  a login before #442 is closed. Until then "that document only" is true of
  what this change opens and false of what such a caller can reach over the
  API. The change can be built and merged before #442; a recipient's login
  cannot be handed out before it.
- **#437** for the check in a real browser: until it is fixed a browser cannot
  post the console's login form, so the local check would have to be done with
  curl only.

## Out of scope

Issuing shares from the console (`console-share`); the document page's PDF
link (`console-pdf-views`, which this change makes work for a recipient but
does not add); the routes that are open to any logged-in caller today (see
design.md, "Found and not changed").
