## ADDED Requirements

### Requirement: A role can be held through a group

A caller SHALL hold a role when a group in their verified identity assertion is
mapped to that role. Groups SHALL be read only from the verified assertion, and
SHALL reach only callers authenticated by that signed assertion: a caller
authenticated by an API key or the `ww_console` cookie has no groups. A
group-held role SHALL gate role-checked actions (such as the delete gate and
role-gated pages) but SHALL NOT by itself authorise a reveal: a reveal still
needs a grant whose recipient is the caller.
The group → role mapping SHALL be managed by a `beheerder` and every change to
it SHALL be audited.

#### Scenario: Group membership grants the role

- **WHEN** a caller's verified assertion lists a group mapped to role R
- **THEN** the caller holds R for role-checked actions, such as the delete gate
  when R is `beheerder`
- **AND** no reveal is authorised by that membership alone: a reveal still
  needs a grant whose recipient is the caller, and `global_by_role` still names
  that person

#### Scenario: A revoked group no longer grants it

- **WHEN** the group is no longer in the caller's assertion
- **THEN** the caller no longer holds R through it and the role-checked action
  is refused

#### Scenario: A forged group is ignored

- **WHEN** a request carries a group in a header or an unsigned token
- **THEN** that group grants nothing

#### Scenario: A group never opens a reveal

- **WHEN** a caller holds role R only through a group and presents a grant id
  whose recipient is someone else
- **THEN** the reveal is refused with the existing 403

#### Scenario: Key and cookie callers have no groups

- **WHEN** a caller is authenticated by an API key or a `ww_console` cookie
- **THEN** no group is attached to them, and a group-gated action is refused
  unless a grant names them for the role

#### Scenario: A group mapped to a switched-off role grants nothing

- **WHEN** a group is mapped to a role that is switched off
- **THEN** a caller holding it only through that group does not hold it
