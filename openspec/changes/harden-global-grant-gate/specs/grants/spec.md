## MODIFIED Requirements

### Requirement: Per-type reveal grants

The system SHALL represent authorization to reveal PII as a grant naming a
recipient and a set of PII types, optionally scoped to a single document and/or an
expiry. A grant SHALL carry no key material and no clear PII. Grants SHALL be
issued and revoked; revocation SHALL be idempotent.

A grant without a document scope ("global") SHALL authorize any document ONLY
where the deployment explicitly allows global grants. Where it does not — the
default — such a grant SHALL authorize nothing, whenever and however it was
issued, and SHALL be refused at issue.

#### Scenario: A grant authorizes only its own types

- **WHEN** a grant for types {PERSON} is asked to authorize a reveal of
  {PERSON, BSN}
- **THEN** it authorizes exactly {PERSON}

#### Scenario: A scoped grant applies only to its own document

- **WHEN** a grant scoped to document D authorizes a reveal
- **THEN** it authorizes for D and authorizes nothing for another document,
  whether or not the deployment allows global grants

#### Scenario: An unscoped grant is inert unless global grants are allowed

- **WHEN** a grant with no document scope is asked to authorize a reveal of its
  allowed types
- **THEN** it authorizes the empty set where the deployment does not allow global
  grants, and its allowed types where it does

### Requirement: Grant admin over HTTP

The API SHALL let an operator issue, inspect, and revoke reveal grants over HTTP,
mounted only when a grant store is configured. Issuing SHALL accept a recipient,
a list of PII types, an optional document scope, and an optional timezone-aware
expiry (a naive or malformed expiry, or a malformed document id, SHALL be
rejected with 400). Issuing without a document scope SHALL be rejected with 400
where the deployment does not allow global grants, writing neither a grant nor an
audit event. Inspecting or revoking an unknown grant SHALL return 404; revoke
SHALL be idempotent. Every issue and revoke SHALL be recorded in the
key-lifecycle audit stream. No response SHALL contain key material or clear PII.

#### Scenario: Issue, inspect, revoke

- **WHEN** an operator issues a grant, then inspects it, then revokes it
- **THEN** issue returns the grant with status active, inspect reflects it, and
  revoke returns status revoked (a second revoke is a no-op)

#### Scenario: Revocation gates reveal

- **WHEN** a grant that authorised a reveal is revoked and the same reveal is
  attempted again
- **THEN** the reveal is refused (the revoked grant authorises nothing)

#### Scenario: An unscoped issue is refused while global grants are disallowed

- **WHEN** an operator issues a grant without a document scope on a deployment
  that does not allow global grants
- **THEN** the request is rejected with 400 and no grant is created

#### Scenario: Absent without a grant store

- **WHEN** the app is configured without a grant store
- **THEN** the grant routes are not mounted
