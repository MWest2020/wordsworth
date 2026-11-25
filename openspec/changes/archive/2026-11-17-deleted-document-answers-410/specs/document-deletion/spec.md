## ADDED Requirements

### Requirement: A deleted document answers 410 on its content routes

For a document whose state is `deleted`, `GET /documents/{document_id}/anonymized`,
`GET /documents/{document_id}/redacted.pdf` and
`POST /documents/{document_id}/feedback` SHALL answer 410 with the body
`{"detail": "document deleted"}`.

The 410 SHALL come after the route's caller gate and before every other answer
about the document: before 409 for a superseded copy, before 409 for a
document that is not yet de-identified, before the box-map answers and before
the render cache is read. A caller the gate refuses SHALL get the gate's 403
for a deleted document exactly as for any other id. An id that was never
registered SHALL keep answering 404.

Request validation SHALL keep its place before both the 404 and the 410, and
SHALL answer a deleted document as it answers any other: 422 for a malformed
document id or request body, and 400 for an unsupported `view` on
`GET /documents/{document_id}/anonymized`.

Whether a document is deleted SHALL be decided from its state alone, never
from the absence of its text, its box map or its object.

The reveal endpoints are governed by the `reveal-api` capability and are not
covered by this requirement. Deleting a deleted document again is governed by
the requirements on repeated deletion and SHALL NOT answer 410.

#### Scenario: The de-identified text of a deleted document

- **WHEN** a corpus reader requests `GET /documents/{document_id}/anonymized`
  for a deleted document
- **THEN** the answer is 410 `document deleted`, not 409

#### Scenario: The redacted PDF of a deleted document

- **WHEN** a corpus reader requests the redacted PDF of a deleted document
  while a cached render of it is still in the object store
- **THEN** the answer is 410 `document deleted` and the render is not served

#### Scenario: A deleted superseded copy

- **WHEN** a corpus reader requests the de-identified text and the redacted
  PDF of a superseded copy that has been deleted
- **THEN** both answers are 410 `document deleted` and neither names the
  surviving document

#### Scenario: A caller without corpus read learns nothing

- **WHEN** a caller who is not a corpus reader requests each of the three
  routes for a deleted document, for a live document and for an unknown id
- **THEN** every answer is the same 403, with the same body

#### Scenario: An unknown id is still unknown

- **WHEN** a corpus reader requests each of the three routes for an id that
  was never registered
- **THEN** the answer is 404

#### Scenario: A request that is not valid is refused as before

- **WHEN** a corpus reader requests `GET /documents/{document_id}/anonymized`
  with an unsupported `view`, for a deleted document, a live document and an
  unknown id
- **THEN** every answer is the same 400, not 410 and not 404

#### Scenario: A document that is not yet de-identified is not called deleted

- **WHEN** a corpus reader requests the de-identified text of a registered
  document that has no text yet and is not deleted
- **THEN** the answer is 409, as before

### Requirement: Feedback on a deleted document is refused

`POST /documents/{document_id}/feedback` SHALL NOT append a record to the
audit chain of a deleted document. A `detection_feedback` record SHALL never
follow a `deleted` record in a document's chain, also when the deletion and
the feedback request run at the same moment. Feedback recorded before the
deletion SHALL remain in the trail.

#### Scenario: Feedback after the deletion

- **WHEN** a corpus reader posts feedback on a deleted document
- **THEN** the answer is 410 `document deleted`, the document's chain has the
  same number of records as before, and the audit chain still verifies

#### Scenario: Feedback while the document is being deleted

- **WHEN** a deletion of a document commits while a feedback request for it
  is in progress
- **THEN** either the feedback record precedes the `deleted` record, or the
  request answers 410 and writes nothing; no `detection_feedback` record
  follows the `deleted` record, and the document's state is `deleted`

#### Scenario: Earlier feedback is kept

- **WHEN** a document that received feedback is deleted
- **THEN** its earlier `detection_feedback` records are unchanged and the
  audit chain still verifies

### Requirement: The record of a deleted document stays readable

`GET /documents/{document_id}/state` and `GET /documents/{document_id}` SHALL
keep answering 200 for a deleted document, to a caller with corpus read: the
state `deleted`, and the document's audit trail with its `deleted` record. They
return no content of the document; they show what a deletion keeps.

#### Scenario: The state of a deleted document

- **WHEN** a corpus reader requests the state of a deleted document
- **THEN** the answer is 200 with state `deleted`

#### Scenario: The trail of a deleted document

- **WHEN** a corpus reader requests `GET /documents/{document_id}` for a
  deleted document
- **THEN** the answer is 200 and its trail contains the `deleted` record with
  the caller and the counts, and no text, value, token or filename
