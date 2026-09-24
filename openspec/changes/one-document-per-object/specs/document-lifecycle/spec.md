## MODIFIED Requirements

### Requirement: Document state machine

Each ingested document SHALL progress through an explicit, ordered set of
states: `registered`, `extractable`, `unprocessable_ocr`, `extracted`,
`anonymized`, `indexed`, `failed`, and `superseded`. A document SHALL be in
exactly one state at any time, and transitions SHALL follow only the defined
edges. `superseded` SHALL be terminal and reachable from every state; it is
the only edge that leaves `indexed` or `failed`.

#### Scenario: New document enters as registered

- **WHEN** a document is stored in object storage and its row is created
- **THEN** its state is `registered` and a `registered` audit record exists

#### Scenario: Undefined transition is rejected

- **WHEN** a transition is attempted that is not a defined edge for the current
  state
- **THEN** the transition is rejected and the document state is unchanged

#### Scenario: An indexed document can be superseded

- **WHEN** an `indexed` document is superseded
- **THEN** its state is `superseded`, and no transition leaves `superseded`

## ADDED Requirements

### Requirement: One live document per stored object

At most one document that is not `superseded` SHALL exist per `object_key`,
enforced by the database. A registration that would create a second one SHALL
return the existing document instead, also when two registrations of the same
bytes run at the same time.

#### Scenario: The same bytes delivered twice at once

- **WHEN** two registrations of the same bytes run concurrently
- **THEN** one document exists for that `object_key`, and both callers get it

#### Scenario: OCR recovery lands on an object that is already a document

- **WHEN** OCR recovery would move a document's `object_key` to an object that
  a live document already holds
- **THEN** the recovering document is superseded in favour of that document

### Requirement: A copy is retired, not removed

A superseded document SHALL keep its row, its audit records and its pseudonym
links, and SHALL name the document that superseded it. Asking for it SHALL
answer `superseded` with that document, not a 404. Reveal on a superseded
document SHALL be refused, naming the surviving document.

#### Scenario: A superseded document is asked for

- **WHEN** a client requests a superseded document by id
- **THEN** the answer says `superseded` and names the surviving document

#### Scenario: Reveal on a copy

- **WHEN** reveal is called on a superseded document
- **THEN** it is refused and names the surviving document, and nothing is
  revealed
