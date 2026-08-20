# reveal-api Specification

## Purpose
TBD - created by archiving change add-reveal-api. Update Purpose after archive.
## Requirements
### Requirement: Key-gated per-type reveal endpoint

The API SHALL expose `POST /documents/{document_id}/reveal` accepting a grant id
and an optional list of PII types. It SHALL reveal only the types the grant
authorises for that document; every other type SHALL remain pseudonymised. When
no types are given, it SHALL reveal exactly the types the grant allows. The
response SHALL report the revealed types and the requested-but-withheld types.
The endpoint SHALL be mounted only when a key provider and grant store are
configured.

#### Scenario: Only the granted type is revealed

- **WHEN** a reveal is requested with a grant that allows one PII type but the
  request asks for two
- **THEN** the response text contains the original for the granted type, the
  other type stays pseudonymised, and the response lists the granted type as
  revealed and the other as withheld

### Requirement: Reveal authorisation and error semantics

The endpoint SHALL return 404 when the document or the grant is unknown, 403 when
the grant is revoked, expired, or scoped to a different document, and 409 when the
document has not been de-identified. A successful reveal SHALL be recorded as an
audited access event whose actor is the grant recipient, carrying the revealed
types and no clear value, leaving the audit chain verifiable.

#### Scenario: A revoked grant is refused

- **WHEN** a reveal is requested with a revoked grant
- **THEN** the endpoint responds 403 and no text is revealed

#### Scenario: Reveal is audited

- **WHEN** a reveal succeeds
- **THEN** a `deanonymize` audit record is appended for that document with the
  grant recipient as actor and the revealed types, containing no clear values,
  and the audit chain still verifies

