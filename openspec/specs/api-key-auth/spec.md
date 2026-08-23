# api-key-auth Specification

## Purpose
TBD - created by archiving change add-api-key-auth. Update Purpose after archive.
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

