## ADDED Requirements

### Requirement: Both kinds of driver implement one interface of operations

wordsworth's in-process drivers and its key service drivers SHALL implement
the same interface of operations (pseudonymise, open an original, delete a
document), not `KeyProvider` or `MappingStore`, and the driver SHALL be chosen
by configuration with the in-process driver as the default. A service driver
SHALL expose no operation that returns key material or ciphertext. Reveal is
not part of the interface.

#### Scenario: One contract, both drivers

- **WHEN** the contract tests run against the in-process and the service driver
- **THEN** both give the same results

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
working. Entering and leaving it SHALL be recorded in the audit trail without
any value.

#### Scenario: A write is refused in maintenance

- **WHEN** maintenance is on and a document is ingested or a grant is changed
- **THEN** the request is refused before anything is written and the state is
  unchanged

#### Scenario: Reads stay up

- **WHEN** maintenance is on and a caller searches, opens the console or reveals
- **THEN** each answers as when maintenance is off

#### Scenario: Off by default

- **WHEN** maintenance has not been switched on
- **THEN** writes are accepted as before
