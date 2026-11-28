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
SHALL keep wordsworth's column names, types and nullability.

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
