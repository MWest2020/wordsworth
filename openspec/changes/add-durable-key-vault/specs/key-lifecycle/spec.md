## ADDED Requirements

### Requirement: Data keys are durably persisted as envelope-wrapped blobs

Data keys SHALL be persisted durably as ciphertext wrapped by an OpenBao Transit
KEK that never leaves OpenBao; only the wrapped material SHALL be stored, never
clear key bytes, and never in logs. A key provider constructed fresh over the same
vault and Transit (e.g. after a process restart) SHALL resolve the same active key
per scope and SHALL resolve any prior version by its `key_id`, so pseudonymised
data stays revealable across restarts.

#### Scenario: A fresh provider resolves persisted keys after a restart

- **WHEN** data is pseudonymised, then a brand-new key provider is constructed over
  the same durable vault and Transit
- **THEN** the new provider resolves the same key material and the data
  deanonymises to its originals

### Requirement: Fail-closed on unwrap failure

If the Transit unwrap of a data key fails, the key provider SHALL raise and SHALL
NOT fall back to any clear or substitute key, so reveal and new-type
pseudonymisation degrade safely rather than leak.

#### Scenario: Unwrap failure raises

- **WHEN** the Transit backend cannot unwrap a stored key
- **THEN** resolving that key raises and no clear key material is produced
