## ADDED Requirements

### Requirement: A role can be held through a group

A caller SHALL hold a role when a group in their verified identity assertion is
mapped to that role and the role is active. Groups SHALL be read only from the
verified assertion of the current request; a header, an unsigned or unverifiable
token, or an expired assertion SHALL contribute no group, and no group SHALL be
remembered beyond the request.

A caller authenticated by API key or by the console cookie SHALL carry no
groups, also when an assertion rides along on the same request: the sent
credential names a label, and a label has no groups.

A group-held role SHALL count only where the system decides by whether a caller
holds a role (today: the delete gate for documents and dossiers). It SHALL NOT
change a gate that decides by a configured label list.

The group → role mapping SHALL be managed behind the same gate as roles, and
every change to it SHALL be audited in the key-lifecycle stream with the person
who made it as actor.

#### Scenario: Group membership opens a role gate

- **WHEN** a caller's verified assertion lists a group mapped to the active role
  `beheerder`, and the caller holds no grant naming it
- **THEN** that caller may delete a document, and the deletion's audit record
  names the caller, not the group

#### Scenario: A revoked group no longer grants it

- **WHEN** the group is no longer in the caller's assertion
- **THEN** the same delete is refused with 403 and nothing is removed

#### Scenario: A forged group is ignored

- **WHEN** a request carries a group in a header or an unsigned token
- **THEN** that group grants nothing

#### Scenario: An expired group assertion grants nothing

- **WHEN** the assertion that lists the group has expired
- **THEN** it yields no caller and no group, and no group from it is held for
  this or any later request

#### Scenario: A console-cookie caller carries no groups

- **WHEN** a person whose only `beheerder` comes from a group signs in to the
  console with the cookie and deletes a document
- **THEN** the delete is refused with 403, because the cookie caller carries no
  groups, and the documentation tells them to use a personal grant or label

#### Scenario: An API-key caller carries no groups

- **WHEN** a request presents a valid API key and also carries a verified
  assertion listing a group mapped to `beheerder`
- **THEN** the caller is the key's label with no groups, and holds `beheerder`
  only if that label holds a grant naming it

#### Scenario: A mapping change is audited with a person

- **WHEN** a group → role mapping is added or removed
- **THEN** the key-lifecycle stream gains one event naming the group, the role
  and the caller who changed it

### Requirement: A group-held role never authorises a reveal

A reveal SHALL remain authorised only by a grant whose recipient is the caller.
Holding a role through a group SHALL NOT make a caller the recipient of any
grant, SHALL NOT supply PII types, and SHALL NOT be an input to the reveal
decision. The reveal audit record SHALL keep naming the grant recipient, a
person, as actor.

#### Scenario: Someone else's grant naming the role is refused

- **WHEN** caller authentication is enabled and a caller whose assertion lists a
  group mapped to `beheerder` presents an unscoped grant naming `beheerder` that
  was issued to a different recipient
- **THEN** the endpoint responds 403, no text is revealed and no `deanonymize`
  record is written

#### Scenario: A group role without a personal grant reveals nothing

- **WHEN** a caller whose assertion lists a group mapped to role R holds no
  grant naming them as recipient for the document
- **THEN** no reveal succeeds for that caller

#### Scenario: A personal grant still works and names the person

- **WHEN** the same caller presents a grant naming role R issued to them
- **THEN** the reveal proceeds exactly as for any recipient, and the
  `deanonymize` record names that caller as actor

### Requirement: A switched-off role opens no gate

Deciding whether a caller holds a role SHALL treat an inactive or unknown role
as held by nobody, whether it would be held through a grant or through a group.
It SHALL NOT fall back to the grant, the group mapping, or any default.

#### Scenario: A grant-held switched-off role opens nothing

- **WHEN** the `beheerder` role is switched off and a caller who holds an
  active, unexpired grant naming it tries to delete a document
- **THEN** the delete is refused with 403 and nothing is removed

#### Scenario: A group-held switched-off role opens nothing

- **WHEN** the `beheerder` role is switched off and a caller whose assertion
  lists a group mapped to it tries to delete a document
- **THEN** the delete is refused with 403 and nothing is removed

#### Scenario: Switching the role back on restores it

- **WHEN** the role is switched on again
- **THEN** both callers may delete again, without any grant or mapping having
  changed
