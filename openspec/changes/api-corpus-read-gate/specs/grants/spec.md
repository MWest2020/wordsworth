## ADDED Requirements

### Requirement: Inspecting a grant is limited to readers and issuers

When caller authentication is on, `GET /grants/{id}` SHALL answer only a caller
who may read the corpus or who may issue grants. Any other caller SHALL get
403, before the grant is looked up, so that the answer does not say whether the
grant exists. Being the recipient of a grant SHALL NOT by itself admit a caller
to inspect it. An admitted caller SHALL get 404 for an unknown grant, as before.

Without caller authentication, and where no corpus-read list is configured,
behaviour SHALL be unchanged.

#### Scenario: A caller on no list cannot inspect a grant

- **WHEN** an authenticated caller who is neither on the corpus-read list nor
  an issuer requests `GET /grants/{id}` for an existing grant and for an
  unknown id
- **THEN** both answer 403 with the same body

#### Scenario: An issuer and a reader can

- **WHEN** an issuer, or a caller on the corpus-read list, requests
  `GET /grants/{id}` for an existing grant
- **THEN** the answer is 200 with the grant, and 404 for an unknown id
