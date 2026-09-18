## ADDED Requirements

### Requirement: An identity comes from a signature, never from a header

When an identity provider sits in front of the application, the caller's identity
SHALL be taken only from a cryptographically verified assertion. A header naming
the user SHALL never be a source of identity.

The readable header and the signed assertion arrive together and look equally
convincing. Only one of them cannot be forged. Trusting the header would make
every path that does not pass the provider — an internal network route, a direct
call to the origin — a way to claim any identity, and those paths exist.

Verification SHALL check the signature against the provider's published keys AND
that the assertion was issued for THIS application. An assertion issued for
another application of the same organisation is not access to this one.

Missing or invalid configuration SHALL yield no identity. It SHALL NOT yield a
warning and an accepted header.

#### Scenario: A forged header grants nothing

- **WHEN** a request carries a header naming a user but no valid signed assertion
- **THEN** no identity is derived from it

#### Scenario: An assertion for another application is refused

- **WHEN** a validly signed assertion names a different audience
- **THEN** it is refused

#### Scenario: Without configuration there is no identity

- **WHEN** the verification is not configured
- **THEN** no identity is derived, and the request is handled as it was before

### Requirement: A verified identity is the caller, unless a key is presented

A verified identity SHALL become the caller recorded in the audit trail.

A credential the caller SENT SHALL take precedence over one that rides along. An
identity provider injects its assertion on every request through it, so without
this order a person behind that provider could never be anything else, and the
way back to a key would exist only on routes that bypass the provider — which
may be exactly the routes they cannot reach. Presenting a key is a deliberate
choice and is honoured; ending that session hands the identity back.

This is not weaker. Both come from the same configured sets, and a forged header
carries no valid key any more than a forged assertion carries a valid signature.

The way to present a key SHALL stay reachable from behind an identity provider.

An audit trail that names a shared key answers "which key was used", not "who
looked". The whole point of putting a person in front of the door is that the
trail can name them.

The key SHALL remain the way in wherever no verified identity is present, so that
an installation running without such a provider keeps working unchanged. A screen
that only opens behind one vendor is not sovereign software.

#### Scenario: The audit names the person

- **WHEN** a reveal is performed by a verified identity
- **THEN** the audit record names that identity as the caller

#### Scenario: A presented key wins over an injected assertion

- **WHEN** a request carries both a valid key and a valid assertion
- **THEN** the key's label is the caller

#### Scenario: The key route stays open from behind the provider

- **WHEN** someone behind an identity provider asks for the key form
- **THEN** they get it, and logging in there takes precedence

#### Scenario: Without a provider the key still works

- **WHEN** a request arrives with no verified identity and a valid key
- **THEN** it is accepted, with the key's label as caller, exactly as before

### Requirement: Grants tied to a key label are named before identities replace them

Turning on identity-based callers SHALL, before it takes effect, report which
existing grants are issued to a key label and therefore authorise nobody once
callers are identities.

Such grants do not become dangerous; they become inert, and an inert grant that
still reads as "active" is a lie in the table. The recipient binding taught this
the expensive way: four grants went quiet and it was noticed afterwards, by
looking.

Reporting SHALL happen before the switch. Re-issuing them to an identity is an
administrator's decision and SHALL NOT happen automatically — moving an
authorisation from a shared key to a person is exactly the judgement a machine
should not make.

#### Scenario: The switch names what it will make inert

- **WHEN** identity-based callers are about to be enabled
- **THEN** the grants issued to key labels are reported first

#### Scenario: Nothing is re-issued on its own

- **WHEN** identity-based callers are enabled
- **THEN** no grant is created, changed or moved to an identity
