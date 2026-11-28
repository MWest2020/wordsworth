## ADDED Requirements

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
