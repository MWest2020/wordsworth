# console-pdf-views

## Why

Mark, 2026-10-28: the key user wants to *"share with layered
anonymisation"*. Redacted PDFs exist for 354 of 415 documents of the dossier
(`GET /documents/{id}/redacted.pdf`), and a reveal PDF with a grant (`POST
/documents/{id}/reveal.pdf`), but the console links neither; the runbook calls
console embedding undecided. The review (docs/explanation/review-key-user-2026-10-28.md) settles it: the document page is
where a key user looks at what they would share.

## What changes

- The document page links "Gelakte PDF" (the redacted PDF) when the document
  has a box map, and says why not when it hasn't (no box map yet; stale).
- Next to each grant's text reveal, a "Onthul als PDF" button posts to the
  reveal PDF with that grant and the checked types.
- Both go through the console's existing auth and the API's existing gates; the
  console adds no second door.

## Out of scope

Issuing grants (`console-share`), embedding a PDF viewer.
