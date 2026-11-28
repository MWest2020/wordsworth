## ADDED Requirements

### Requirement: The switch is verified and reversible by configuration

Moving keys, mappings and authorisation facts into the key service SHALL be
verified before wordsworth switches to it. The in-process drivers and the old
tables SHALL stay, so that setting the drivers back restores the old behaviour.

#### Scenario: A mismatch aborts

- **WHEN** a copied mapping does not decrypt to the same value, or an original
  does not open
- **THEN** the switch aborts and wordsworth keeps the old drivers

#### Scenario: Rollback is configuration

- **WHEN** the drivers are set back to in-process inside the verification window
- **THEN** wordsworth works as before the switch

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
- **THEN** the switch aborts and wordsworth keeps the old drivers

#### Scenario: Every document's domain is copied

- **WHEN** a document's copied domain differs from its `register` record
- **THEN** the switch aborts and wordsworth keeps the old drivers

### Requirement: Roles, group mappings and grants are managed through the key service

After the switch the key service's management endpoints SHALL be the way roles,
group mappings and grants are changed, and wordsworth's grant and role routes
and the console SHALL call them.

#### Scenario: A grant change goes through the service

- **WHEN** a grant is created through wordsworth's route or the console
- **THEN** it is made by the key service's management endpoint
