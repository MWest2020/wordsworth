## ADDED Requirements

### Requirement: Grants may be issued by PPL level

`POST /grants` SHALL accept `ppl` (integer 0–3) as an alternative to
`allowed_types`. The server SHALL expand `ppl` via the PII category registry and
persist the result as `allowed_types`; the stored grant model is unchanged.
Supplying both or neither SHALL be rejected with 422.

#### Scenario: PPL shorthand is expanded on issue

- **WHEN** a grant is issued with `ppl: 1`
- **THEN** the stored `allowed_types` equals the registry's PPL 1 set and the
  response reports `ppl: 1`

#### Scenario: Both forms at once are rejected

- **WHEN** a grant request carries both `ppl` and `allowed_types`
- **THEN** the API responds 422 and no grant is created
