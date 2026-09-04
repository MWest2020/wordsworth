## ADDED Requirements

### Requirement: Tokens are derived from the normalised value

The keyed pseudonym SHALL be derived from `normalize(label, value)` rather than
the raw value, where `normalize` applies a typed, table-driven rule set (default:
trim + Unicode NFC; BSN: strip separators, left-pad to 9 digits; postcode: strip
spaces, uppercase; names, locations, organisations and e-mail addresses: trim,
NFC, casefold; dates: ISO 8601 when parseable, else the default). The encrypted mapping SHALL still hold the original value.

#### Scenario: Spelling variants yield one pseudonym

- **WHEN** `Jansen` and `jansen` are pseudonymised under the same key
- **THEN** both produce the same token

#### Scenario: BSN formatting variants yield one pseudonym

- **WHEN** `1234.56.789` and `123456789` are pseudonymised under the same key
- **THEN** both produce the same token

### Requirement: One stored original per token

The mapping store SHALL hold exactly one encrypted original per token: the
spelling first seen under that token (idempotent put). Reveal SHALL return that
stored spelling; a later variant that normalises onto the same token is
represented by it. The normalised form itself SHALL never be stored.

#### Scenario: First-seen spelling is what reveal returns

- **WHEN** `Jansen` is pseudonymised and later `jansen` collides onto its token
- **THEN** reveal of either document returns `Jansen`

### Requirement: Normalisation profile is versioned

Every mapping row SHALL record the normalisation profile version used. A change
to the rule set SHALL bump the version; re-deriving an existing corpus SHALL go
through the reprocess path, never happen implicitly.

#### Scenario: Version is stored

- **WHEN** a pseudonym is stored
- **THEN** the mapping row carries the current profile version
