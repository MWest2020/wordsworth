## ADDED Requirements

### Requirement: A role can be held through a group

A caller SHALL hold a role when a group in their verified identity assertion is
mapped to that role. Groups SHALL be read only from the verified assertion.
The group → role mapping SHALL be managed by a `beheerder` and every change to
it SHALL be audited.

#### Scenario: Group membership grants the role

- **WHEN** a caller's verified assertion lists a group mapped to role R
- **THEN** a reveal authorised by R succeeds for that caller

#### Scenario: A revoked group no longer grants it

- **WHEN** the group is no longer in the caller's assertion
- **THEN** the same reveal is refused

#### Scenario: A forged group is ignored

- **WHEN** a request carries a group in a header or an unsigned token
- **THEN** that group grants nothing
