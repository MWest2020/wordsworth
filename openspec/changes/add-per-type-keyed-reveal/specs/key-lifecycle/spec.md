## ADDED Requirements

### Requirement: Keys are scoped per PII type

The `KeyProvider` SHALL support an optional scope on `current_key` and `rotate`,
identifying a PII type, defaulting to a single global scope when omitted (backward
compatible). Each scope SHALL have its own active key and its own rotation history;
`key(key_id)` SHALL resolve any version regardless of scope so stored mappings
decrypt by their `key_id` as before.

#### Scenario: Rotating one scope leaves other scopes' active keys unchanged

- **WHEN** the provider is rotated for one PII-type scope
- **THEN** that scope has a new active key while other scopes' active keys are
  unchanged, and all prior versions across scopes remain resolvable by `key_id`
