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

### Requirement: Both kinds of driver implement one interface of operations

wordsworth's in-process drivers and its key service drivers SHALL implement
the same interface of operations (pseudonymise, open an original, delete a
document), not `KeyProvider` or `MappingStore`, and the driver SHALL be chosen
by configuration with the in-process driver as the default. A service driver
SHALL expose no operation that returns key material or ciphertext.

#### Scenario: One contract, both drivers

- **WHEN** the contract tests run against the in-process and the service driver
- **THEN** both give the same results

#### Scenario: Nothing configured changes nothing

- **WHEN** no driver is configured
- **THEN** wordsworth uses the in-process drivers

### Requirement: Tokens are stable only while the key vault moves intact

The key service and wordsworth share `Pseudonymizer` and `DurableKeyProvider`,
so the same value SHALL give the same token through either only when the service
holds the same keys (ids, material, scopes). The cutover SHALL NOT switch
pseudonymisation to the service before the vault has been copied and verified.

#### Scenario: The same vault gives the same token

- **WHEN** a value is pseudonymised in-process and, after the vault is copied,
  through the service
- **THEN** both tokens are equal

#### Scenario: A different key gives a different token

- **WHEN** one key's material in the service differs from wordsworth's
- **THEN** the token differs, which is why the verification compares decryptions

### Requirement: After the switch of a key operation the key service alone performs it

Once wordsworth uses the key service's driver for pseudonymise, originals,
open-limits or delete, the key service SHALL be the only component that
performs that operation's key work, and wordsworth SHALL build no key provider,
Transit client or OpenBao credential for it. No route SHALL return a clear
value to wordsworth's service credential without a verified person. Reveal is
excepted until its own change switches it.

#### Scenario: wordsworth holds no key for a switched operation

- **WHEN** wordsworth runs with the key service's drivers for pseudonymise,
  originals, open-limits and delete
- **THEN** it builds no key provider, Transit client or OpenBao credential for
  them, and each of those operations goes through the key service

#### Scenario: The copied registry is complete

- **WHEN** a live document's current text holds a token that is missing from
  the copied registry for that document
- **THEN** the cutover aborts and wordsworth keeps the old drivers
