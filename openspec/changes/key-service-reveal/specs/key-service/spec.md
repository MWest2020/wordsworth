## ADDED Requirements

### Requirement: The key service decides a reveal from its own facts

The key service SHALL decide a reveal from its own grants, roles, record of
each document's domain and token registry, and SHALL reveal a token only when
it was requested, is registered for the document in question, is of a type the
caller is authorised for, and its encrypted value and key are present. Nothing
the calling service sends SHALL widen what is revealed.

#### Scenario: Another document's token is not revealed

- **WHEN** a caller covered for document A with type PERSON asks to reveal a
  PERSON token that is registered only for document B
- **THEN** that token is not revealed and the answer does not name it

#### Scenario: Only authorised types

- **WHEN** a caller whose grant allows PERSON asks for PERSON and IBAN
- **THEN** only PERSON tokens are revealed and IBAN is reported as withheld

#### Scenario: The PDF view carries no values

- **WHEN** a reveal is asked with the PDF view
- **THEN** the answer lists the resolved tokens and contains no clear value

### Requirement: The key service verifies the person itself

The key service SHALL verify the person's signed assertion itself (signature,
issuer, its own configured audience, validity window) and SHALL NOT accept an
identity from a header or from the calling service's token. It SHALL always
check that the person is the grant's recipient.

#### Scenario: A forged identity is refused

- **WHEN** a reveal carries a forged, expired or foreign-audience assertion
- **THEN** the service answers 401, reads no grant, document or mapping, and
  decrypts nothing

#### Scenario: A service token is not a person

- **WHEN** a reveal carries a valid service token and no assertion
- **THEN** it is refused and nothing is decrypted

### Requirement: The grant is decided before any document fact

Both reveal endpoints of the key service SHALL judge the grant on its own
domain before reading anything about the document, and SHALL answer every
caller it does not cover with 403 `{"detail": "grant not applicable"}`, the
same status and body whatever the cause, including an unknown or deleted
document. Deletion SHALL be told only to a covered caller. The service SHALL
never answer 404 or 409 on these endpoints. The decision endpoint SHALL
decrypt nothing and write nothing, and the reveal endpoint SHALL decide again
without relying on an earlier decision.

#### Scenario: A grant that does not apply reads nothing about the document

- **WHEN** a decide or reveal call carries an unknown, revoked, expired or
  other-recipient grant, or a grant for another document
- **THEN** the answer is the uniform refusal and no statement reads the
  service's document, registry, mapping or key tables

#### Scenario: All causes give one answer

- **WHEN** a caller who is not covered asks about an unknown document, a
  document in another domain and a deleted document
- **THEN** every answer has the same status, body and content type

#### Scenario: A grant revoked between the calls

- **WHEN** a grant is revoked after a successful decide and before the reveal
- **THEN** the reveal is refused and nothing is decrypted

### Requirement: A reveal in the key service is audited, a refusal leaves no trace

Every successful reveal SHALL append one record to the service's audit stream
naming the calling service, the person, the grant's recipient, the grant, the
requested, authorised and resolved types and the resolved tokens, with no
clear value. A refused reveal SHALL write no record and SHALL log nothing that
names its cause or the document's existence or state.

#### Scenario: The reveal is on the record

- **WHEN** a reveal succeeds
- **THEN** one audit record holds its tokens and types and no value, the
  answer's resolved types equal the record's, and the chain verifies

#### Scenario: A refusal is silent about its cause

- **WHEN** reveals are refused for an unknown, a deleted and an out-of-scope
  document
- **THEN** the audit stream is unchanged and the captured logs are the same
  for each apart from the document id
