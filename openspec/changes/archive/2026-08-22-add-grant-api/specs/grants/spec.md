## ADDED Requirements

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
