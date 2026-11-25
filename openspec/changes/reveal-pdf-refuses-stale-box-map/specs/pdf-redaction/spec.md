## ADDED Requirements

### Requirement: The reveal PDF refuses a stale box map

`POST /documents/{document_id}/reveal.pdf` SHALL answer 409 with the body
`{"detail": "stale"}` when the current `lists_hash` differs from the one the
document's box map was made with. It SHALL decide this by the same check, and
answer with the same status and body, as
`GET /documents/{document_id}/redacted.pdf`.

A request refused as stale SHALL reveal nothing: no mapping SHALL be
decrypted, the original SHALL NOT be read, and no `deanonymize` audit record
SHALL be appended.

Only a caller the grant covers for that document SHALL be told the box map is
stale. Any other caller SHALL get the answer he would get if the box map were
current.

After `reanonymize` has regenerated the box map under the current lists, the
endpoint SHALL serve the reveal PDF again. `POST /documents/{document_id}/reveal`
SHALL NOT be affected by the state of the box map.

#### Scenario: A lists change, then stale, then reanonymize

- **WHEN** the detection lists change so that they detect a value in a
  document that has no box in its box map, the recipient of a grant on that
  document for another type calls the reveal PDF, `reanonymize` is run, and
  he calls it again
- **THEN** the first call answers 409 `stale` and returns no PDF, and the
  last call serves a PDF in which the newly detected value is boxed

#### Scenario: A stale refusal reveals and records nothing

- **WHEN** the recipient of a grant that covers a document calls the reveal
  PDF while the document's box map is stale
- **THEN** the answer is 409 `stale`, the document has the same number of
  audit records as before the request, the audit chain still verifies, and no
  mapping was decrypted

#### Scenario: The same answer as the redacted PDF

- **WHEN** a document's box map is stale and a caller who is both a corpus
  reader and the recipient of a grant on it requests the redacted PDF and the
  reveal PDF
- **THEN** both answers have status 409 and the same body

#### Scenario: A caller the grant does not cover hears nothing about staleness

- **WHEN** a caller presents, for a document whose box map is stale, a grant
  that does not cover it (unknown, revoked, expired, scoped to another
  document, or issued to another recipient)
- **THEN** the answer has the same status and body as the same request gets
  when the box map is current, and the body does not contain `stale`

#### Scenario: A current box map is served as before

- **WHEN** the recipient of a grant calls the reveal PDF for a document whose
  box map was made under the current lists
- **THEN** the PDF is served as before, with one `deanonymize` record carrying
  `view=pdf`

#### Scenario: The text reveal is not affected

- **WHEN** the recipient of a grant calls `POST /documents/{document_id}/reveal`
  for a document whose box map is stale
- **THEN** the reveal answers as it does for a document whose box map is
  current
