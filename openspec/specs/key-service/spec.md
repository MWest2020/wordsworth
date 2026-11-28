# key-service Specification

## Purpose
Created by the change `key-service-skeleton`. ADR-0009 (accepted 2026-10-30, amended 2026-11-26): one service holds the keys,

## Requirements

### Requirement: The key service runs as its own process on its own database

The key-and-reveal service SHALL run as a separate process with its own
configuration and its own database, which the rest of wordsworth cannot read.
It SHALL refuse to start when it has no database configured, when its database
is the one wordsworth is configured with, or when its database holds a table
only wordsworth has. It SHALL NOT read wordsworth's settings module; it SHALL
read wordsworth's database URL from the environment only in order to refuse
it.

#### Scenario: Pointed at wordsworth's database

- **WHEN** the service or its init entrypoint is configured with wordsworth's
  database
- **THEN** it refuses to start, names the rule, and creates nothing

#### Scenario: A database that holds wordsworth's tables

- **WHEN** the configured database contains `audit_records` or
  `document_texts`
- **THEN** the service refuses to start

#### Scenario: wordsworth's settings are ignored

- **WHEN** both `WORDSWORTH_*` and `KEYSERVICE_*` values are set and differ
- **THEN** the service uses the `KEYSERVICE_*` values

#### Scenario: wordsworth's settings module is never read

- **WHEN** the service's tests run with wordsworth's `config.settings` made to
  raise on every access
- **THEN** they pass

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

### Requirement: Only an authenticated calling service reaches the API

Every `/v1` route SHALL require a service token from the configured set and
SHALL refuse a missing or unknown token with 401 before reading the request
body or the database. With no token configured, every `/v1` call SHALL be
refused. A service token SHALL identify a calling service, never a person.

#### Scenario: No token

- **WHEN** a `/v1` route is called without a service token or with an unknown
  one
- **THEN** the service answers 401 and reads nothing from its database

#### Scenario: Nothing configured means closed

- **WHEN** the service runs with no service token configured
- **THEN** every `/v1` call is refused with 401

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

- **WHEN** a document first pseudonymised in domain A is pseudonymised in
  domain B
- **THEN** the service answers 409 and changes nothing

#### Scenario: A batch over the cap is refused

- **WHEN** a batch holds more items than the configured maximum
- **THEN** the service answers 422 and registers nothing

### Requirement: Only reveal returns a clear value

No route of the key service other than reveal SHALL return a clear value from
the mapping store, and reveal SHALL need a verified person.

#### Scenario: No value without a person

- **WHEN** a calling service uses every route of the service with only its
  service token
- **THEN** no response contains a clear value from the mapping store

### Requirement: Opening an original names a purpose, is audited and fails closed

Every opening of an original SHALL name a purpose from a fixed list and SHALL
be audited with that purpose. A wrapped key or sealed object that fails to
authenticate SHALL fail closed. Sealing SHALL record the document's domain on
first sight and refuse a different domain afterwards, as pseudonymising does.

#### Scenario: No purpose, no open

- **WHEN** an open names no purpose or one outside the list
- **THEN** it is refused with 422 and nothing is decrypted

#### Scenario: A tampered key fails closed

- **WHEN** the wrapped data key or the sealed object has been altered
- **THEN** the open is refused, no plaintext is returned, and the failure is
  audited

#### Scenario: Seal and open stay in separate modules within the line limit

- **WHEN** the service's originals routes are built
- **THEN** seal is in `api_originals.py` and open is in `api_open.py`, and
  every module of the change is at most 200 lines

#### Scenario: A sealed document keeps its domain

- **WHEN** a document first pseudonymised or sealed in domain A is sealed in
  domain B
- **THEN** the service answers 409 and changes nothing

### Requirement: Opening an original is rate-limited per calling service

Every opening of an original SHALL be subject to a rate limit per calling
service.

#### Scenario: A burst is refused

- **WHEN** a calling service opens originals faster than its limit
- **THEN** the excess is refused with 429, every refusal is counted in the
  metrics, and the audit records the burst once per caller per window with its
  count

### Requirement: Service-only state has one home outside the audit

State that only the key service has, the open-refusal counter and the rate-limit
window state, SHALL live in one table, `service_state`, SHALL NOT be derived
from the audit, and SHALL be guarded by a test that fails when such state
appears elsewhere.

#### Scenario: A counter outside the home is caught

- **WHEN** a table other than `service_state` gains a counter or window column
- **THEN** the service-state drift test fails and names the table

### Requirement: Volume metrics need the service token and are never rate-limited

The key service SHALL expose its open and refusal counters at `/v1/metrics`,
under the same service-token check as every other route, and SHALL NOT
rate-limit that route.

#### Scenario: Metrics without a token

- **WHEN** `GET /v1/metrics` is called without a valid service token
- **THEN** the service answers 401 and exposes no counter

#### Scenario: Scraping is never refused

- **WHEN** `/v1/metrics` is called repeatedly with a valid token
- **THEN** no call is answered 429

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
