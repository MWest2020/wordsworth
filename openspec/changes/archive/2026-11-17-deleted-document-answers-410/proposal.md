# deleted-document-answers-410

## Why

A deleted document answers differently on every route that takes its id
(issue #456, from the review of #453). Measured against the code at
origin/main `8577ece`, for a caller who passes the route's own gate:

| Route | Today, for a deleted document |
|---|---|
| `GET /documents/{id}/anonymized` | 409 `document not yet de-identified` (the text is gone, so the route thinks it has not been made yet) |
| `POST /documents/{id}/feedback` | 201, and a `detection_feedback` record is appended to the chain after its `deleted` record |
| `GET /documents/{id}/redacted.pdf` | 410 `document deleted` (since #453; in the code, in no spec) |
| `POST /documents/{id}/reveal.pdf` | 410 before the grant check (an oracle; `reveal-authorize-first`, #494, replaces it) |
| `POST /documents/{id}/reveal` | 404 `unknown grant`, or 409 for a deleted superseded copy, or 409 `not yet de-identified` |
| `GET /documents/{id}/state`, `GET /documents/{id}` | 200, state `deleted` and the trail |

"Not yet de-identified" tells a client to wait for something that will never
come. And a deletion is terminal by spec ("A deleted document stays deleted"),
yet the audit chain of a deleted document can still grow by anybody's
feedback.

## What changes

- The routes that return or accept a document's content answer 410
  `{"detail": "document deleted"}` for a deleted document:
  `GET /documents/{id}/anonymized`, `GET /documents/{id}/redacted.pdf` (now
  specified) and `POST /documents/{id}/feedback`.
- The 410 comes after the route's caller gate and before every other answer
  about the document. A caller the gate refuses gets its 403, deleted or not.
  A deleted superseded copy answers 410, not 409 `superseded`.
- Feedback on a deleted document is refused and writes nothing, also when the
  deletion lands while the feedback request is running. Today that race can
  put a feedback record after the `deleted` record, after which the document
  reads as `indexed` again (design.md, decision 5; read from the code, not
  reproduced).
- The two routes that show what a deletion keeps, `GET /documents/{id}/state`
  and `GET /documents/{id}`, keep answering 200 with state `deleted` and the
  trail. That is the default of question #501 (`waiting-on-mark`); see
  design.md, decision 2.
- A test lists every route with a document id in its path together with its
  answer for a deleted document, and fails on a route without one.

| Route, for a caller who passes its gate | before | after |
|---|---|---|
| `GET /documents/{id}/anonymized` | 409 `not yet de-identified` | 410 `document deleted` |
| `POST /documents/{id}/feedback` | 201, record appended | 410 `document deleted`, nothing appended |
| `GET /documents/{id}/redacted.pdf` | 410 | 410 (specified) |
| `GET /documents/{id}/state` | 200 `deleted` | same |
| `GET /documents/{id}` | 200 with the trail | same |
| `DELETE /documents/{id}` | 200, finishes what is left | same |

## What does not change

- The reveal routes. `reveal-authorize-first` (#494) specifies them: the
  uniform 403 to a caller the grant does not cover, 410 on both routes to one
  it covers. This change adds nothing there and does not restate it, so the
  two cannot disagree. #456's "checked first" would bring back the oracle
  #487 removes if applied to them literally.
- Deleting a deleted document again: the `document-deletion` spec makes the
  rerun finish leftover work (keys, scans, renders). It is not a 410.
- The console page of a deleted document (`/console/documents/{id}`): the
  console spec says it still opens.
- An unknown id: 404. The corpus-read gate: 403 before any lookup.
- Routes without a document id in the path (search, export, reprocess, the
  dossier and topic routes): they already skip deleted documents.

## Capabilities

- `document-deletion`: three requirements added.

## Depends on / order

- Builds on `api-corpus-read-gate` (#485, merged): "after the gate" is its
  declared dependency.
- Independent of `reveal-authorize-first` (#494) in the code: the reveal
  routes are not touched. Its inventory row for the two reveal routes points
  at that change (design.md, decision 6).
- Composes with `share-recipient-read` (#439): a recipient whose grant the
  deletion removed is refused by the document-read gate (403), a reader gets
  410.

## Out of scope

The reveal routes (#487/#494); the stale box map on `reveal.pdf` (#438, change
`reveal-pdf-refuses-stale-box-map`); #442 (specified and built as
`api-corpus-read-gate`, #485); what `GET /documents/{id}/anonymized` answers
for a superseded copy.
