## ADDED Requirements

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
