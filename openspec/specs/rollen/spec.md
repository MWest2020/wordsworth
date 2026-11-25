# rollen Specification

## Purpose

Wie welke PII mag zien, en dat op één plek kunnen intrekken.

Een rol is **een naam plus een verzameling PII-types**. De scope — dit document
of alles — zit niet in de rol maar in de grant, dus die kies je bij het
toekennen: dezelfde rol kan aan de een gegeven worden voor één document en aan
de ander voor alles.

Een rol is een **ding en geen sjabloon**, en het verschil zit in wat er gebeurt
als je hem uitzet. Een sjabloon kopieert zijn types bij het toekennen naar de
grant; uitzetten wordt dan een opruimactie met een tijdvenster erin, precies op
het moment dat je er geen wilt. Hier wordt de rol opgelost op het moment dat
`authorize()` beslist: uit is uit, onmiddellijk, en er verandert geen enkele
grant.

Daarom staat hier ook wat een rol níet mag zijn: een pad langs `authorize()`
(ook niet voor de beheerder — dat is de tweede deur die het meest gebruikt wordt
en het minst bekeken), een terugval wanneer hij onbekend of uitgezet is (dat zou
van uitzetten een suggestie maken), of een wijziging die niemand kan
navertellen.

Wat hier niet woont, is **wie iemand is**. Dat komt uit de aanmelding, en de dag
dat rollidmaatschap ergens anders vandaan komt, hoort alleen dat punt te
veranderen en niet de beslissing.

## Requirements

### Requirement: A role names a set of PII types, and can be switched off

The system SHALL support named roles, each holding a set of PII types and an
active/inactive state.

A grant MAY name a role instead of a type list. Authorisation SHALL resolve the
role at the moment it decides, not at the moment the grant was issued.

Resolving at decision time is what makes switching a role off mean something.
Resolving at issue time would copy the types into the grant, and turning the role
off would then leave every copy standing — you would believe you had closed
something that is still open.

An inactive role SHALL resolve to no types at all. It SHALL NOT fall back to the
grant's own list, to a previous version of the role, or to any default.

#### Scenario: Switching a role off closes every grant that names it

- **WHEN** a role is switched off
- **THEN** a reveal under a grant naming that role authorises nothing, without
  any grant being modified

#### Scenario: Narrowing a role narrows what its grants authorise

- **WHEN** a type is removed from a role
- **THEN** a reveal under a grant naming that role no longer authorises that type

#### Scenario: A grant with its own type list is unaffected

- **WHEN** a grant names types directly
- **THEN** it behaves exactly as before

### Requirement: Seeing everything is a role, not a bypass

An administrator's ability to see all PII types SHALL be expressed as a role
holding those types, and every reveal an administrator performs SHALL pass the
same authorisation and produce the same audit record as any other reveal.

A special path for administrators is the second door this system does not have.
It is also the one that gets used most and reviewed least.

#### Scenario: An administrator's reveal is an ordinary reveal

- **WHEN** an administrator reveals PII
- **THEN** it passes the same authorisation and is audited identically

#### Scenario: Switching off the administrator role stops it too

- **WHEN** the administrator role is switched off
- **THEN** an administrator reveal authorises nothing

### Requirement: An unscoped grant is allowed by role, not by a flag

A grant that names no document SHALL be permitted when it names the
administrator role, and SHALL stay refused otherwise.

Seeing everything means every type AND every document, and the second half is an
unscoped grant — which was deliberately closed off, because one such grant reveals
the whole corpus. Reopening it with a setting would reopen it for every unscoped
grant in order to open it for one role. The exception belongs on the role, where
it carries the name of whoever holds it instead of hiding behind a boolean.

An audit trail SHALL therefore be able to show afterwards that an exception
applied and to whom.

#### Scenario: The administrator role may hold an unscoped grant

- **WHEN** a grant naming the administrator role and no document is issued
- **THEN** it is accepted

#### Scenario: Any other unscoped grant stays refused

- **WHEN** a grant naming no document and not the administrator role is issued
- **THEN** it is refused, exactly as before

### Requirement: Pulling the emergency stop is recorded

Switching a role off SHALL record who did it and why, and the record SHALL be
part of the same append-only trail as every other event.

An emergency stop without a record is an outage nobody can explain afterwards.
The reason is required for the same result the reason on a combination is
required for: in a year, the only way to judge whether it was right is to know
what it was for.

#### Scenario: A switch-off without a reason is refused

- **WHEN** a role is switched off without a reason
- **THEN** it is refused and the role stays active

#### Scenario: The trail names who pulled it

- **WHEN** a role has been switched off
- **THEN** the trail names the caller, the role and the reason

### Requirement: The first administrator comes from installation, not from the role system

Installing the system SHALL establish exactly one administrator, and every other
role assignment SHALL be made by an administrator.

A role system cannot hand out its own first role without either letting anyone
claim it or deadlocking. Naming installation as the origin makes the bootstrap an
explicit moment instead of a gap — the same reason a root account is not created
by a user manager.

That one identity is therefore the whole of the system's authority at the start,
and SHALL be recorded as such: who it is, and when it was established.

The origin of roles SHALL NOT be assumed to stay here. A production deployment is
expected to delegate identity and role assignment to an external provider, and
nothing in this capability may depend on roles being defined locally.

#### Scenario: Installation establishes one administrator

- **WHEN** the system is installed
- **THEN** exactly one administrator exists, and its establishment is recorded

#### Scenario: Nobody assigns themselves a role

- **WHEN** someone who is not an administrator assigns a role
- **THEN** it is refused, whoever they are and whichever role it is

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
