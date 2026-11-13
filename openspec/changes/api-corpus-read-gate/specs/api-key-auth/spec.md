## ADDED Requirements

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
labelling a topic, computing summaries. A refused write SHALL leave no trace:
no audit record, no changed row.

Where the corpus-read list is empty the scope is off and behaviour SHALL be
unchanged. Where no caller authentication is configured behaviour SHALL be
unchanged. A caller on the list SHALL get the answers he got before.

The write path (`POST /ingest`, `POST /reprocess`, `POST
/datasets/pseudonymize`) is not covered by this requirement.

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
  `POST /topics/{id}/label` or `POST /dossiers/{id}/summaries`
- **THEN** each answers 403, and no audit record, topic or summary was written
  or changed

#### Scenario: A reader is unaffected

- **WHEN** a caller on the corpus-read list requests the same routes
- **THEN** each answers as it did before this requirement

#### Scenario: The key the thin client and an orchestrator use still works

- **WHEN** a caller whose label is on the corpus-read list, as the `cli` and
  `console` labels are, searches, exports and reads a document's state, and a
  caller with any valid key uploads a document to `POST /ingest`
- **THEN** every one of those requests is answered as before

#### Scenario: An empty list changes nothing

- **WHEN** no corpus-read list is configured
- **THEN** every authenticated caller gets the answers he got before

### Requirement: A corpus-read refusal comes before the lookup

A caller without corpus read SHALL be refused before the route looks anything
up or validates the query, so that the answer is the same 403 for an id that
exists and one that does not, and for a complete and an incomplete request.

#### Scenario: An unknown document is refused, not reported

- **WHEN** a caller who is not on the corpus-read list requests
  `GET /documents/{id}/state` or `GET /documents/{id}`, or sends
  `POST /documents/{id}/feedback`, for an id that does not exist
- **THEN** the answer is 403 and not 404, with the same body as for an id that
  exists

#### Scenario: A missing parameter is refused, not explained

- **WHEN** that caller requests `GET /search` without a query or a dossier
- **THEN** the answer is 403

### Requirement: Every route has a recorded access decision

Every route the application mounts SHALL be recorded in one inventory with the
check it applies: corpus read, grant read, grant issue, delete, decided by a
grant, any authenticated caller, or open. The test suite SHALL fail when a
mounted route is missing from the inventory, when an inventory entry names a
route that is not mounted, when an API route recorded as corpus read does not
declare that check, and when a route does not refuse a caller its entry says it
refuses.

Routes that stay reachable without corpus read SHALL be exactly those the
inventory records as such, each with its reason: the liveness probe and the
metrics endpoint without any key; the login page and its assets without any
key; logout, the root redirect and the API schema for any authenticated caller.

#### Scenario: A new route without a decision fails the suite

- **WHEN** a route is added to the application and not to the inventory
- **THEN** the test suite fails and names the route

#### Scenario: A route that loses its check fails the suite

- **WHEN** the corpus-read check is removed from a route the inventory records
  as corpus read
- **THEN** the test suite fails

#### Scenario: The probes stay open

- **WHEN** authentication and a corpus-read list are configured
- **THEN** `GET /health` and `GET /metrics` answer without a key, and the login
  page answers without a key
