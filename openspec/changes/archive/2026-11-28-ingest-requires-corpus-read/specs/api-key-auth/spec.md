## MODIFIED Requirements

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

## ADDED Requirements

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
