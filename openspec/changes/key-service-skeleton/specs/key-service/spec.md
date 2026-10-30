## ADDED Requirements

### Requirement: One service holds keys, values and the reveal decision

The key-and-reveal service SHALL be the only component that holds key material,
talks to the key-encryption service, stores the encrypted values behind tokens,
or decides a reveal. It SHALL use its own database, which the rest of
wordsworth cannot read.

#### Scenario: Pseudonymising returns tokens only

- **WHEN** a batch of values is pseudonymised through the service
- **THEN** the response contains tokens and no value

#### Scenario: Its own database

- **WHEN** the service is configured with wordsworth's database
- **THEN** it refuses to start

### Requirement: The service verifies identity itself

The service SHALL authenticate its service callers and SHALL verify a caller's
identity assertion itself; it SHALL NOT accept an identity from a header.

#### Scenario: A forged identity is refused

- **WHEN** a reveal carries a forged, expired or foreign-audience assertion
- **THEN** it is refused and nothing is decrypted

### Requirement: Opening an original is audited

Every opening of an original SHALL be audited with its purpose and SHALL be
subject to a rate limit per service caller.

#### Scenario: A burst is refused

- **WHEN** a service caller opens originals faster than its limit
- **THEN** the excess is refused and the refusals are audited
