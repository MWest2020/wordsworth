## MODIFIED Requirements

### Requirement: Keys are scoped per PII type

Data keys SHALL be scoped per `domain/type`, where `domain` identifies a
pseudonymisation domain (e.g. a department) and `type` the PII type. The default
domain SHALL be `_global`; existing key rows scoped by type alone SHALL be read
as `_global/<type>` without migration. The same value under two domains SHALL
yield two different pseudonyms. Rotation, escrow and recovery operate per scope.

#### Scenario: Domains do not share pseudonyms

- **WHEN** the same BSN is pseudonymised in domain `wi` and in domain `mo`
- **THEN** the two tokens differ

#### Scenario: Legacy scope keeps working

- **WHEN** a key row scoped `PERSON` exists from before this change
- **THEN** it is used for `_global/PERSON` and existing tokens still reveal

## ADDED Requirements

### Requirement: Grants are domain-bound

A grant MAY name a domain. A grant without a domain SHALL authorise reveal in
`_global` only; it SHALL never match all domains implicitly.

#### Scenario: Grant without domain is fail-safe

- **WHEN** a grant without `domain` is used to reveal a document ingested in
  domain `wi`
- **THEN** every type is withheld
