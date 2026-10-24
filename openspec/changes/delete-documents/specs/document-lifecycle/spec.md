## MODIFIED Requirements

### Requirement: Document state machine

Each ingested document SHALL progress through an explicit, ordered set of
states: `registered`, `extractable`, `unprocessable_ocr`, `extracted`,
`anonymized`, `indexed`, `failed`, `superseded`, and `deleted`. A document SHALL
be in exactly one state at any time, and transitions SHALL follow only the
defined edges. `superseded` SHALL be terminal and reachable from every state; it
is the only edge that leaves `indexed` or `failed` other than `deleted`.
`deleted` SHALL be terminal and reachable from every state, including
`superseded`.

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

#### Scenario: A deleted document stays deleted

- **WHEN** a document has been deleted
- **THEN** its state is `deleted` and no transition leaves `deleted`
