## MODIFIED Requirements

### Requirement: A copy is retired, not removed

A superseded document SHALL keep its row, its audit records and its pseudonym
links, and SHALL name the document that superseded it. Asking for it SHALL
answer `superseded` with that document, not a 404. Reveal on a superseded
document SHALL be refused. The refusal SHALL name the surviving document only to
a caller the reveal grant covers for that document; to any other caller it SHALL
be the reveal API's uniform refusal, which names nothing.

#### Scenario: A superseded document is asked for

- **WHEN** a client requests a superseded document by id
- **THEN** the answer says `superseded` and names the surviving document

#### Scenario: Reveal on a copy

- **WHEN** the recipient of a grant that covers a superseded document calls
  reveal on it
- **THEN** it is refused and names the surviving document, and nothing is
  revealed

#### Scenario: Reveal on a copy by a caller the grant does not cover

- **WHEN** reveal is called on a superseded document with a grant that does not
  cover it (unknown, revoked, expired, scoped elsewhere, or issued to another
  recipient)
- **THEN** it is refused with the uniform refusal, the answer names no surviving
  document, and nothing is revealed
