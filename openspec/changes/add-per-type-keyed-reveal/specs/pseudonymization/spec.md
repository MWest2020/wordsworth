## ADDED Requirements

### Requirement: Per-type keyed pseudonyms

Each PII type SHALL be pseudonymised under its own type-scoped key, so that the
token and the encrypted mapping for a value of type T depend on T's active key.
Possession of T's key SHALL be necessary and sufficient to decrypt T's mappings,
and SHALL NOT decrypt another type's mappings. The search index SHALL still see
only pseudonyms.

#### Scenario: Different types use different keys

- **WHEN** values of two different PII types are pseudonymised
- **THEN** each type's mapping is encrypted under that type's own key, and the key
  for one type does not decrypt the other type's mappings

### Requirement: Selective reveal by type

Deanonymisation SHALL accept an optional set of allowed PII types. A token SHALL be
revealed only when its type is allowed AND the caller can resolve that mapping's
key; otherwise the token SHALL remain in place, unrevealed. When no allowed set is
given, all resolvable tokens SHALL be revealed (unchanged behaviour). The
deanonymisation audit record SHALL additionally record which types were revealed,
and SHALL NOT record any clear value.

#### Scenario: Only allowed types are revealed

- **WHEN** a document containing two PII types is deanonymised with only one type
  allowed
- **THEN** tokens of the allowed type are replaced by their originals and tokens of
  the other type remain pseudonymised

#### Scenario: A type whose key is unavailable stays pseudonymised

- **WHEN** a type is allowed but the caller cannot resolve that type's key
- **THEN** that type's tokens remain pseudonymised (no partial or failed decrypt)
