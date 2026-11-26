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

### Requirement: After the switch the key service is the only component holding key material

Once wordsworth uses the key service's drivers, the key service SHALL be the
only component that holds key material, talks to the key-encryption service,
or can turn a token into a value. wordsworth SHALL hold no key provider,
Transit client or OpenBao credential, and no route SHALL return a clear value
to wordsworth's service credential without a verified person.

#### Scenario: wordsworth holds no key

- **WHEN** wordsworth runs with the key service's drivers
- **THEN** it builds no key provider, Transit client or OpenBao credential,
  and every key operation goes through the key service

#### Scenario: The copied registry is complete

- **WHEN** a live document's current text holds a token that is missing from
  the copied registry for that document
- **THEN** the cutover aborts and wordsworth keeps the old drivers
