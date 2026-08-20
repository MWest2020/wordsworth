# grants Specification

## Purpose
TBD - created by archiving change add-reveal-grants. Update Purpose after archive.
## Requirements
### Requirement: Per-type reveal grants

The system SHALL represent authorization to reveal PII as a grant naming a
recipient and a set of PII types, optionally scoped to a single document and/or an
expiry. A grant SHALL carry no key material and no clear PII. Grants SHALL be
issued and revoked; revocation SHALL be idempotent.

#### Scenario: A grant authorizes only its own types

- **WHEN** a grant for types {PERSON} is asked to authorize a reveal of
  {PERSON, BSN}
- **THEN** it authorizes exactly {PERSON}

#### Scenario: A global grant applies to any document; a scoped grant only to its own

- **WHEN** a grant scoped to document D authorizes a reveal
- **THEN** it authorizes for D and authorizes nothing for another document, while a
  grant with no document scope authorizes for any document

### Requirement: Revocation and expiry withhold authorization

A revoked grant SHALL authorize nothing. A grant past its expiry SHALL authorize
nothing. Authorization SHALL be a pure decision returning the permitted subset of
the requested types (empty when denied), never raising for the denied case.

#### Scenario: Revoked grant authorizes nothing

- **WHEN** a grant is revoked and then asked to authorize its previously allowed
  type
- **THEN** it authorizes the empty set

#### Scenario: Expired grant authorizes nothing

- **WHEN** the current time is at or past a grant's expiry
- **THEN** it authorizes the empty set, while before the expiry it authorizes its
  allowed types

### Requirement: Grant issue and revoke are audited without key material

Issuing and revoking a grant SHALL each append an event to the append-only
key-lifecycle audit stream (not the document hash-chain), recording the grant id,
recipient, allowed types, and actor. No key material SHALL ever be written.

#### Scenario: Issue and revoke each write one audit event

- **WHEN** a grant is issued and later revoked
- **THEN** the key-lifecycle stream gains one issue event and one revoke event
  naming the grant and actor, and no key material appears in the stream

