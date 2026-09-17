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

### Requirement: A verified identity is the caller, and replaces the second login

A verified identity SHALL become the caller recorded in the audit trail, and the
console SHALL NOT ask for a key from someone who already has one.

An audit trail that names a shared key answers "which key was used", not "who
looked". The whole point of putting a person in front of the door is that the
trail can name them.

The key SHALL remain the way in wherever no verified identity is present, so that
an installation running without such a provider keeps working unchanged. A screen
that only opens behind one vendor is not sovereign software.

#### Scenario: The audit names the person

- **WHEN** a reveal is performed by a verified identity
- **THEN** the audit record names that identity as the caller

#### Scenario: A verified identity is not asked for a key

- **WHEN** a verified identity opens the console
- **THEN** it is not shown the key form

#### Scenario: Without a provider the key still works

- **WHEN** a request arrives with no verified identity and a valid key
- **THEN** it is accepted, with the key's label as caller, exactly as before
