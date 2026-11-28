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

### Requirement: Corpus read is required wherever the corpus is returned or changed

Where a corpus-read list is configured, every route that returns corpus content
or corpus metadata SHALL require the caller to be on that list, and SHALL
answer 403 to any other caller, also when that caller is authenticated. Corpus
metadata is what says which documents exist, their state, what they are about,
which PII types they carry, and who was granted what on them. This SHALL hold
for the API and for the console alike: search, hybrid search, question
answering, both exports, a document's text, redacted PDF, metadata and state,
a dossier's topics and summaries, and the declared combinations.

A route that changes what a reader sees of the corpus SHALL require the same:
recording detection feedback on a document, computing or renaming topics,
labelling a topic, computing summaries, re-de-identifying documents
(`POST /reprocess`), and adding documents (`POST /ingest`), which creates
documents and dossiers and puts documents into dossiers that readers search.
A refused write SHALL leave no trace: no audit record, no changed row, no
stored object.

Where the corpus-read list is empty the scope is off and behaviour SHALL be
unchanged. Where no caller authentication is configured behaviour SHALL be
unchanged. A caller on the list SHALL get the answers he got before.

#### Scenario: A caller on no list is refused on every reading route

- **WHEN** a corpus-read list is configured and an authenticated caller who is
  not on it requests `GET /search`, `GET /hybrid`, `GET /ask`,
  `GET /export/ranking.csv`, `GET /export/anonymized.zip`,
  `GET /documents/{id}`, `GET /documents/{id}/state`,
  `GET /documents/{id}/anonymized`, `GET /documents/{id}/redacted.pdf` or
  `GET /dossiers/{id}/topics`
- **THEN** each answers 403

#### Scenario: A caller on no list cannot change what readers see

- **WHEN** that caller sends `POST /documents/{id}/feedback`,
  `POST /dossiers/{id}/topics`, `PATCH /topics/{id}`,
  `POST /topics/{id}/label`, `POST /dossiers/{id}/summaries` or
  `POST /reprocess`, with or without a list of document ids
- **THEN** each answers 403, no audit record, topic or summary was written or
  changed, and no document was re-de-identified

#### Scenario: A caller on no list cannot add documents

- **WHEN** a corpus-read list is configured and an authenticated caller who is
  not on it, a grant issuer who is no reader included, uploads a PDF to
  `POST /ingest`, into a new dossier or an existing one
- **THEN** the answer is 403, and no document, dossier, dossier membership,
  audit record or stored object was written

#### Scenario: A reader is unaffected

- **WHEN** a caller on the corpus-read list requests the same routes
- **THEN** each answers as it did before this requirement

#### Scenario: The key the thin client and an orchestrator use still works

- **WHEN** a caller whose label is on the corpus-read list, as the `cli` and
  `console` labels are, searches, exports, reads a document's state, starts
  a reprocess run and uploads a document to `POST /ingest`
- **THEN** every one of those requests is answered as before

#### Scenario: An empty list changes nothing

- **WHEN** no corpus-read list is configured
- **THEN** every authenticated caller gets the answers he got before, an
  upload to `POST /ingest` included

### Requirement: A corpus-read refusal comes before the lookup

A caller without corpus read SHALL be refused before the route looks anything
up or validates the path and the query, so that the answer is the same 403 for
an id that exists and one that does not, and for a complete and an incomplete
request. One answer MAY come first: a request body that is not well-formed
JSON is answered 422 to any caller, before the check, because the body is
parsed before the caller is judged. That answer SHALL NOT depend on the corpus.

#### Scenario: An unknown document is refused, not reported

- **WHEN** a caller who is not on the corpus-read list requests
  `GET /documents/{id}/state` or `GET /documents/{id}`, or sends
  `POST /documents/{id}/feedback`, for an id that does not exist
- **THEN** the answer is 403 and not 404, with the same body as for an id that
  exists

#### Scenario: A missing parameter is refused, not explained

- **WHEN** that caller requests `GET /search` without a query or a dossier
- **THEN** the answer is 403

#### Scenario: A malformed body says nothing about the corpus

- **WHEN** that caller sends `PATCH /topics/{id}` with a body that is not JSON,
  for an id that exists and for one that does not
- **THEN** both answer 422 with the same body, and nothing is changed

### Requirement: Every route has a recorded access decision

Every route the application mounts SHALL be recorded in one inventory with the
check it applies and the reason: corpus read, grant read, grant issue, delete,
decided by a grant, any authenticated caller, or open.

The test suite SHALL fail when a mounted route is missing from the inventory,
when an inventory entry names a route that is not mounted, when an API route
recorded as corpus read does not declare that check, and when a route does not
refuse a caller its entry says it refuses. So that no route escapes the
comparison, the suite SHALL also fail when the application under test was
built without one of its optional backends, when a container of routes (an
included router or a mounted application) was not descended into, when a route
object of a kind the comparison does not know is present, and when a WebSocket
route is present, since those are not authenticated. `HEAD` SHALL be treated as
the `GET` of the same route.

A route that writes (any method other than `GET` and `HEAD`) SHALL be recorded
behind a check that refuses a caller on no list, or as decided by a grant. The
suite SHALL fail for a writing route recorded as any authenticated caller or
as open, unless it is named, with its reason, among the open writes; the only
open write is the console's login form.

Routes that need no corpus read SHALL be exactly those the inventory records
as such, each with its reason:

- without any key: the liveness probe, the metrics endpoint, the login page
  and the console's static assets;
- for any authenticated caller: logout, the root redirect and the API schema;
- behind another check: the routes that issue, revoke and inspect grants and
  manage roles, `POST /datasets/pseudonymize` (grant issue), the two delete
  routes (delete), and the two reveal routes (the grant itself).

#### Scenario: A new route without a decision fails the suite

- **WHEN** a route is added to the application and not to the inventory
- **THEN** the test suite fails and names the route

#### Scenario: A route that loses its check fails the suite

- **WHEN** the corpus-read check is removed from a route the inventory records
  as corpus read
- **THEN** the test suite fails

#### Scenario: A writing route without a check fails the suite

- **WHEN** a route that writes is recorded in the inventory as open to any
  authenticated caller, and is not the console's login form
- **THEN** the test suite fails and names the route

#### Scenario: A backend the test does not mount fails the suite

- **WHEN** the application gains an optional backend that mounts routes, and
  the test's application is built without it
- **THEN** the test suite fails and names the parameter

#### Scenario: A WebSocket route fails the suite

- **WHEN** a WebSocket route is added to the application
- **THEN** the test suite fails

#### Scenario: The probes stay open

- **WHEN** authentication and a corpus-read list are configured
- **THEN** `GET /health` and `GET /metrics` answer without a key, and the login
  page answers without a key

### Requirement: A dataset run requires the grant-issue right

When caller authentication is on, `POST /datasets/pseudonymize` SHALL answer
only a caller who may issue grants, and SHALL answer 403 to any other caller,
corpus readers included, before the upload is processed. A dataset run returns
the token of every value it is given, made with the same keys and in the same
domain as the tokens in documents; a caller who can see tokens could use it to
confirm which value a token stands for, which is what a grant is for. A
refused run SHALL leave no document row, no audit record and no mapping.

Without caller authentication behaviour SHALL be unchanged.

#### Scenario: A reader who is no issuer cannot look a value up

- **WHEN** a caller on the corpus-read list who is not an issuer, or a caller
  on no list, uploads a CSV with a column of names to
  `POST /datasets/pseudonymize`
- **THEN** the answer is 403, no token is returned, and no document row, audit
  record or mapping was written

#### Scenario: An issuer runs a dataset as before

- **WHEN** an issuer uploads the same CSV
- **THEN** the answer is 200 with the pseudonymised CSV, as before

### Requirement: An unverified address is not an identity

When the caller is established from an OIDC token, the token SHALL carry
`email_verified` with the value `true`; a token where it is absent, false or
of another type SHALL yield no caller, as a token with a wrong signature does.
The read list and the grants name callers by address, so an address nobody
verified must not be one. An assertion from Cloudflare Access, which carries
no such claim and establishes the address itself, SHALL be accepted as before.
A caller who also presents a valid key SHALL still be that key's caller.

#### Scenario: An unverified address names nobody

- **WHEN** a correctly signed OIDC token for the configured issuer and
  audience carries the address of a caller on the corpus-read list and
  `email_verified` false, or no `email_verified` at all
- **THEN** the request has no caller: 401 for a program, the login page for a
  browser

#### Scenario: A verified address is the caller

- **WHEN** the same token carries `email_verified` true
- **THEN** the caller is that address

### Requirement: An empty read list is said out loud

When caller authentication is on, a grant store is configured and the
corpus-read list is empty, the application SHALL log a warning at startup that
the corpus-read scope is off and every authenticated caller reads the corpus.
It SHALL still start, and SHALL answer as before.

#### Scenario: Authentication and grants without a read list

- **WHEN** the application starts with API keys or an identity provider, a
  grant store, and no corpus-read list
- **THEN** one warning naming the empty list is logged, and requests are
  answered as before

#### Scenario: A configured list is silent

- **WHEN** the application starts with a corpus-read list
- **THEN** no such warning is logged

### Requirement: An upload is refused before it is read

A caller who may not ingest SHALL be refused by `POST /ingest` before the
request body is read or parsed, so that the upload of a refused caller is not
spooled, validated or processed. A missing or unknown key SHALL still be
answered 401, as before.

#### Scenario: The upload of a refused caller is not read

- **WHEN** an authenticated caller who is not on the corpus-read list sends a
  multipart upload to `POST /ingest`
- **THEN** the answer is 403 and the request body was not parsed

#### Scenario: No key is still 401

- **WHEN** authentication is configured and a request to `POST /ingest`
  carries no key and no verified identity
- **THEN** the answer is 401, as before
