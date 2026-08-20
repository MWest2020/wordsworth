## ADDED Requirements

### Requirement: Reversible mode is config-selected and off by default

The deployed application SHALL select reversible pseudonymisation via
configuration, defaulting to OFF. When off, the pipeline SHALL use the
irreversible anonymizer and SHALL NOT mount the reveal route (unchanged
behaviour). When on, the pipeline SHALL pseudonymise reversibly (durable keyed
tokens) and SHALL mount the key-gated reveal route. In both modes the search
index SHALL contain only pseudonyms, never clear PII. Turning the flag on SHALL
NOT require any key-store network I/O at process start.

#### Scenario: Default deployment is unchanged

- **WHEN** the app is built with reversible mode off
- **THEN** no reveal route is mounted and the pipeline uses the irreversible
  anonymizer

#### Scenario: Reversible mode mounts reveal and pseudonymises reversibly

- **WHEN** the app is built with reversible mode on
- **THEN** the reveal route is available, and documents ingested through it are
  stored as durable keyed pseudonyms that a later grant-gated reveal can recover

#### Scenario: Reveal survives a restart

- **WHEN** a document is pseudonymised in one request and revealed in a later one
- **THEN** a freshly built key provider resolves the durable keys and reveals the
  granted types
