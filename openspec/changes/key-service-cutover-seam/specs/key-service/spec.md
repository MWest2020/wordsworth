## ADDED Requirements

### Requirement: Both kinds of driver implement one interface of operations

wordsworth's in-process drivers and its key service drivers SHALL implement
the same interface of operations (pseudonymise, open an original, delete a
document), not `KeyProvider` or `MappingStore`, and the driver SHALL be chosen
by configuration with the in-process driver as the default. A service driver
SHALL expose no operation that returns key material or ciphertext. Reveal is
not part of the interface.

The interface SHALL state a transaction contract. Each operation is atomic on
its own: it has its whole effect or none. The in-process driver SHALL run in
the caller's database transaction, so its effect is rolled back when the caller
rolls back. A service driver SHALL commit in the key service's own transaction
before it answers, so its effect is not undone by a later rollback of the
caller. A caller SHALL NOT assume that an operation shares its transaction.

#### Scenario: One contract, both drivers

- **WHEN** the contract tests run against the in-process and the service driver
- **THEN** both give the same results

#### Scenario: The in-process driver rolls back with the caller

- **WHEN** an operation runs through the in-process driver and the caller then
  rolls back its transaction
- **THEN** the effect of the operation is gone

#### Scenario: The service driver does not roll back with the caller

- **WHEN** an operation has returned through the service driver and the caller
  then rolls back its own transaction
- **THEN** the effect of the operation stays in the key service

#### Scenario: Nothing configured changes nothing

- **WHEN** no driver is configured
- **THEN** wordsworth uses the in-process drivers

#### Scenario: An unknown driver refuses to start

- **WHEN** the configured driver is neither the in-process nor the service one
- **THEN** wordsworth refuses to start and does not fall back to another driver

### Requirement: Tokens are the same only while the key vault is the same

The key service and wordsworth share `Pseudonymizer` and `DurableKeyProvider`,
so the same value SHALL give the same token through either only when the
service holds the same keys (ids, material, scopes).

#### Scenario: The same vault gives the same token

- **WHEN** a value is pseudonymised in-process and, with the vault copied into
  the service's database, through the service
- **THEN** both tokens are equal

#### Scenario: A different key gives a different token

- **WHEN** one key's material in the service differs from wordsworth's
- **THEN** the token differs

### Requirement: Maintenance mode pauses writes and keeps reads up

wordsworth SHALL have a maintenance mode, off by default, in which ingest and
grant and role changes are refused with a retryable answer that names
maintenance and nothing is written, while search, the console and reveal keep
working. The mode SHALL be a runtime switch held in state shared by all
replicas, not an environment setting, so a script can turn it on and off and
every replica follows without a restart. The refusal SHALL come before the
request body is read, as the `/ingest` read gate does. Entering and leaving it
SHALL be recorded in the audit trail without any value.

#### Scenario: A write is refused in maintenance

- **WHEN** maintenance is on and a document is ingested or a grant is changed
- **THEN** the request is refused before anything is written and the state is
  unchanged

#### Scenario: The refusal comes before the body is read

- **WHEN** maintenance is on and an ingest upload arrives
- **THEN** the refusal is sent before any of the upload is read

#### Scenario: Every replica follows the switch

- **WHEN** maintenance is switched on while two replicas run
- **THEN** both refuse writes at once, without a restart of either

#### Scenario: Reads stay up

- **WHEN** maintenance is on and a caller searches, opens the console or reveals
- **THEN** each answers as when maintenance is off

#### Scenario: Off by default

- **WHEN** maintenance has not been switched on
- **THEN** writes are accepted as before
