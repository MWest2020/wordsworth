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

### Requirement: Grant admin over HTTP

The API SHALL let an operator issue, inspect, and revoke reveal grants over HTTP,
mounted only when a grant store is configured. Issuing SHALL accept a recipient,
a list of PII types, an optional document scope, and an optional timezone-aware
expiry (a naive or malformed expiry, or a malformed document id, SHALL be
rejected with 400). Inspecting or revoking an unknown grant SHALL return 404;
revoke SHALL be idempotent. Every issue and revoke SHALL be recorded in the
key-lifecycle audit stream. No response SHALL contain key material or clear PII.

#### Scenario: Issue, inspect, revoke

- **WHEN** an operator issues a grant, then inspects it, then revokes it
- **THEN** issue returns the grant with status active, inspect reflects it, and
  revoke returns status revoked (a second revoke is a no-op)

#### Scenario: Revocation gates reveal

- **WHEN** a grant that authorised a reveal is revoked and the same reveal is
  attempted again
- **THEN** the reveal is refused (the revoked grant authorises nothing)

#### Scenario: Absent without a grant store

- **WHEN** the app is configured without a grant store
- **THEN** the grant routes are not mounted

### Requirement: Grants may be issued by PPL level

`POST /grants` SHALL accept `ppl` (integer 0–3) as an alternative to
`allowed_types`. The server SHALL expand `ppl` via the PII category registry and
persist the result as `allowed_types`; the stored grant model is unchanged.
Supplying both or neither SHALL be rejected with 422.

#### Scenario: PPL shorthand is expanded on issue

- **WHEN** a grant is issued with `ppl: 1`
- **THEN** the stored `allowed_types` equals the registry's PPL 1 set and the
  response reports `ppl: 1`

#### Scenario: Both forms at once are rejected

- **WHEN** a grant request carries both `ppl` and `allowed_types`
- **THEN** the API responds 422 and no grant is created

