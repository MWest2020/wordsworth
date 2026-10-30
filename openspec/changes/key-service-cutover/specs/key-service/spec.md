## ADDED Requirements

### Requirement: Cutover is verified and reversible

Moving keys, mappings and authorisation facts into the key service SHALL be
verified before wordsworth switches to it, and SHALL be reversible until the
old tables are dropped after a verification window.

#### Scenario: A mismatch aborts

- **WHEN** a copied mapping does not decrypt to the same value, or a sample
  reveal differs
- **THEN** the cutover aborts and wordsworth keeps the old drivers

#### Scenario: After the window nothing sensitive is left behind

- **WHEN** the old tables are dropped after the window
- **THEN** wordsworth's database user can read no key, mapping or grant
