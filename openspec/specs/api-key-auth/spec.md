# api-key-auth Specification

## Purpose

Knowing which caller is on the other end — optional in general, required where it
counts.

Authentication is optional because wordsworth also runs as an engine inside a
trusted boundary, and demanding keys there buys nothing. But it is not optional
in effect: **the authenticated caller is recorded on reveal.** An identity that
came back out of the system without a name attached to the request is the one
audit gap that cannot be reconstructed afterwards.

## Requirements

### Requirement: Optional per-caller API-key authentication

The API SHALL support optional per-caller authentication via API keys configured
as `label:key` pairs. When no keys are configured, authentication SHALL be off
and every endpoint SHALL remain reachable without credentials (unchanged
behaviour). When keys are configured, every endpoint except the ops probes
(`/health`, `/metrics`) SHALL require a valid `X-API-Key` header; a missing or
unknown key SHALL yield 401. Key values SHALL NOT be logged or returned.

#### Scenario: Open when unconfigured

- **WHEN** no API keys are configured
- **THEN** a request without any key header succeeds as before

#### Scenario: Required when configured

- **WHEN** API keys are configured
- **THEN** a request to a protected endpoint with no or an invalid `X-API-Key`
  is rejected with 401, and a request with a valid key succeeds

#### Scenario: Ops probes stay open

- **WHEN** API keys are configured
- **THEN** `/health` is still reachable without a key

### Requirement: Authenticated caller recorded on reveal

When API-key auth is enabled, a reveal SHALL record the authenticated caller's
label in the deanonymise audit record, in addition to (not replacing) the grant
recipient and grant id, and SHALL NOT record any clear PII.

#### Scenario: Reveal audit names the caller

- **WHEN** an authenticated caller reveals a document through a grant
- **THEN** the `deanonymize` audit record carries the caller's label and the
  grant recipient, and contains no clear PII value

### Requirement: Fetching the issuer's keys must not block startup

Fetching the discovery document or the JWKS SHALL NOT happen during startup, but
on the first request that verifies a token, with a cache. If the fetch fails,
that request SHALL yield no caller and the application SHALL keep running. The
JWKS address MAY be configured separately; the discovery document SHALL then not
be fetched, and the issuer SHALL still be checked against `iss`. Every HTTP call
SHALL send a User-Agent.

#### Scenario: The provider is unreachable

- **GIVEN** a configured issuer that does not answer
- **WHEN** the application starts and a request with a token arrives afterwards
- **THEN** the application runs, that request yields no caller, and the rest of
  the API keeps working

#### Scenario: An internal JWKS address

- **GIVEN** a JWKS address configured on an internal Service
- **WHEN** a token is verified
- **THEN** that address is used, no discovery document is fetched, and the
  issuer is still checked against `iss`

### Requirement: Identity comes from a configurable OIDC issuer

The API SHALL be able to establish the caller from a signed OIDC token of a
configured issuer, checking the signature, the issuer, the audience and the
expiry. Cloudflare Access SHALL remain one possible filling-in of that
configuration. The token SHALL be read from `Authorization: Bearer …` or from
`cf-access-jwt-assertion`; an email address from a header SHALL never be
trusted. Without a valid token and without a valid API key there SHALL be no
caller.

Issuer and audience are both required before an OIDC verifier exists at all: a
JWKS address on its own is the *address* of the keys, not the decision to use
them.

#### Scenario: A valid Keycloak token

- **GIVEN** an issuer `https://iam.westerweel.work/realms/westerweel` and
  audience `wordsworth`
- **WHEN** a request arrives with a valid token from that issuer
- **THEN** the caller is the verified email address from the token

#### Scenario: A token from another issuer

- **GIVEN** the same configuration
- **WHEN** the token comes from another issuer, names another audience, or has
  expired
- **THEN** there is no caller, and the request may not issue a grant or read
  full text

#### Scenario: Only an email header

- **WHEN** a request sends only an email address in a header, without a signed
  token
- **THEN** there is no caller
