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

### Requirement: De sleutels van de uitgever halen mag het opstarten niet blokkeren

Het ophalen van het discovery-document of de JWKS SHALL niet tijdens het
opstarten gebeuren, maar bij het eerste verzoek dat een token
controleert, met cache. Mislukt het ophalen, dan SHALL het verzoek geen
caller opleveren en SHALL de applicatie blijven draaien. Het JWKS-adres
MAY los ingesteld worden; dan SHALL het discovery-document niet
opgehaald worden en SHALL de uitgever nog steeds tegen `iss`
gecontroleerd worden. Elke HTTP-aanroep SHALL een User-Agent meesturen.

#### Scenario: Provider onbereikbaar

- **GIVEN** een ingestelde uitgever die niet antwoordt
- **WHEN** de applicatie start en daarna een verzoek met token binnenkomt
- **THEN** draait de applicatie, levert dat verzoek geen caller op, en
  blijft de rest van de API gewoon werken

#### Scenario: Intern JWKS-adres

- **GIVEN** een ingesteld JWKS-adres op een interne Service
- **WHEN** een token gecontroleerd wordt
- **THEN** wordt dat adres gebruikt, wordt er geen discovery-document
  opgehaald, en wordt de uitgever nog steeds tegen `iss` gecontroleerd
