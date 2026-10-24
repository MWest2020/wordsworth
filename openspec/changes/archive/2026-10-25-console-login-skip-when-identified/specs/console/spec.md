## MODIFIED Requirements

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
The login page cannot be behind authentication, so it SHALL use the same
verification as the middleware: when the request carries a verified assertion
the page SHALL send the browser on to `/console` instead of asking for a key,
unless the key form is asked for explicitly with `?key=1`, which SHALL always
show it. A missing or invalid assertion SHALL show the form.

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

#### Scenario: An identified caller is not asked for a key

- **WHEN** `/console/login` is requested with a verified assertion and without
  `?key=1`
- **THEN** it is answered with a 303 to `/console`

#### Scenario: The key form can always be asked for

- **WHEN** `/console/login?key=1` is requested with a verified assertion
- **THEN** the key form is shown

#### Scenario: No or an invalid assertion shows the form

- **WHEN** `/console/login` is requested with no assertion, or one that fails
  verification
- **THEN** the key form is shown
