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
- The 403 page links that page, so a recipient who logs in and lands on a
  refusal has somewhere to go.
- The decision is one function, `auth.authorize_document_read`, next to
  `authorize_corpus_read`. Two places call it: the redacted-PDF route and the
  console document page.

## What does not change

- Search, the document list, dossiers, topics, the feedback overview, the
  export and `GET /documents/{id}/anonymized` stay behind the corpus-read list.
  A recipient gets 403 there as before.
- A grant without a document scope (`document_id IS NULL`) is not a share and
  opens nothing here, whatever the deployment allows for reveals.
- Revealing: `POST /documents/{id}/reveal` and `/reveal.pdf` are decided by the
  grant alone today and stay that way. Nothing is added to them.
- A caller on the corpus-read list sees what he saw before.

## Out of scope

Issuing shares from the console (`console-share`); the document page's PDF
link (`console-pdf-views`, which this change makes work for a recipient but
does not add); the routes that are open to any logged-in caller today (see
design.md, "Found and not changed").
