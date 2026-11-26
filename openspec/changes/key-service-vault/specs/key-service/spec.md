## ADDED Requirements

### Requirement: Pseudonymising returns tokens and fills the service's registry

The key service SHALL turn a document's (type, value) pairs into tokens, store
the encrypted values, and register each returned token for that document in
its own registry. The response SHALL contain tokens only. The registry SHALL be
written only by the service's own pseudonymise (and by the cutover's verified
copy), SHALL never lose a token when a document is pseudonymised again, and
SHALL record each document's domain on first sight and refuse a different
domain afterwards. A batch SHALL hold at most the configured number of items.

#### Scenario: Tokens only

- **WHEN** a batch of values is pseudonymised for a document
- **THEN** the response holds one token per value and no value

#### Scenario: The token is registered for that document

- **WHEN** a value is pseudonymised for document A
- **THEN** its token is in the registry for A and for no other document

#### Scenario: A document keeps its domain

- **WHEN** a document first pseudonymised in domain A is pseudonymised or
  sealed in domain B
- **THEN** the service answers 409 and changes nothing

#### Scenario: A batch over the cap is refused

- **WHEN** a batch holds more items than the configured maximum
- **THEN** the service answers 422 and registers nothing

### Requirement: Deleting a document removes its keys, tokens, orphaned values and scoped grants

Deleting a document in the key service SHALL destroy its data keys, remove its
registry rows, every encrypted value no other document is registered for and
every grant scoped to that document, and keep only a tombstone with the
document's id and domain. A value another
document still holds SHALL survive, also when that other document is being
pseudonymised at the same moment.

#### Scenario: A shared value survives

- **WHEN** a document is deleted while another document holds the same token
- **THEN** that token's encrypted value remains and the other document's
  registry row is untouched

#### Scenario: Deleted means unopenable

- **WHEN** a document's keys have been destroyed
- **THEN** no sealed object of the document can be decrypted by the service

#### Scenario: Grants scoped to the document go with it

- **WHEN** a document with a grant scoped to it and an unscoped grant is
  deleted
- **THEN** the scoped grant is gone, the unscoped one remains, and the answer
  reports one grant deleted

### Requirement: Locks are taken in one order, key lifecycle before audit

Every writer of the key service's database SHALL take its locks in one
documented order, in which the key-lifecycle chain is taken before the audit
chain and the audit chain is the last lock of any transaction.

#### Scenario: Two deletes and a seal do not deadlock

- **WHEN** a document deletion, an originals deletion and a seal run against
  each other
- **THEN** all complete and none is aborted by a deadlock

### Requirement: Service-only state has one home outside the audit

State that only the key service has, the open-refusal counter and the rate-limit
window state, SHALL live in one table, `service_state`, SHALL NOT be derived
from the audit, and SHALL be guarded by a test that fails when such state
appears elsewhere.

#### Scenario: A counter outside the home is caught

- **WHEN** a table other than `service_state` gains a counter or window column
- **THEN** the service-state drift test fails and names the table

### Requirement: Volume metrics need the service token

The key service SHALL expose its counters at `/v1/metrics`, under the same
service-token check as every other route.

#### Scenario: Metrics without a token

- **WHEN** `GET /v1/metrics` is called without a valid service token
- **THEN** the service answers 401 and exposes no counter

### Requirement: Only reveal returns a clear value

No route of the key service other than reveal SHALL return a clear value from
the mapping store, and reveal SHALL need a verified person.

#### Scenario: No value without a person

- **WHEN** a calling service uses every route of the service with only its
  service token
- **THEN** no response contains a clear value from the mapping store

## MODIFIED Requirements

### Requirement: The key service's schema is its own

The service SHALL create its schema from its own metadata, which SHALL
contain no table of wordsworth's metadata and no reference to any wordsworth
table. Its audit tables
SHALL be append-only. Tables whose rows the cutover copies from wordsworth
SHALL keep wordsworth's column names, types and nullability. State that only
the service has (counters, rate-limit windows) SHALL live in `service_state`,
not in a copy of a wordsworth table.

#### Scenario: Init creates only the service's tables

- **WHEN** the init entrypoint runs on an empty database
- **THEN** exactly the service's tables exist, including the token registry,
  and no wordsworth table does

#### Scenario: The audit cannot be changed

- **WHEN** an UPDATE or DELETE is issued on the service's audit tables
- **THEN** the database refuses it

#### Scenario: A drifted copy is caught

- **WHEN** a copied table's column differs in name, type or nullability from
  wordsworth's model
- **THEN** the drift test fails and names the column
