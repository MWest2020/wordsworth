## ADDED Requirements

### Requirement: Keys leave only wrapped

Keys SHALL be exportable only re-wrapped under a receiving key supplied with
the request, by a `beheerder`, and every export and import SHALL be audited
without key material.

#### Scenario: No receiving key, no export

- **WHEN** an export is requested without a valid receiving key
- **THEN** it is refused and no key is unwrapped

#### Scenario: The bundle holds no clear key

- **WHEN** a domain's keys are exported
- **THEN** the bundle contains no clear key bytes, and importing it elsewhere
  lets that installation open the domain's mappings and originals
