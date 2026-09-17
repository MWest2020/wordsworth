# console Specification

## Purpose
TBD - created by archiving change document-console. Update Purpose after archive.

## Requirements

### Requirement: The console shows the artefact, never the original

The console SHALL render the text the pipeline produced after pseudonymisation,
with its tokens marked and typed. It SHALL NOT render the original text and
SHALL NOT resolve a token.

Re-identification has exactly one door: the grant-gated, audited reveal. An
inspection screen that may also reveal is a second door with a friendlier name,
and it is the one nobody audits.

#### Scenario: A document page shows pseudonymised text

- **WHEN** an operator opens a document in the console
- **THEN** the page shows the stored pseudonymised text with each token marked
  and labelled by type, and contains no original value

#### Scenario: The console is not mounted without authentication

- **WHEN** the application starts without API authentication configured
- **THEN** the console routes are absent, and requesting one gives 404

### Requirement: A combination is established where the documents are read

The console SHALL let an operator record a combination of PII types with a
reason, and SHALL show, at the moment of recording, in how many documents every
type of that combination occurs.

Establishing which types identify together depends on the population and the
context, so it is the reader's judgement and not the developer's. A rule that
lives only in a file a developer edits is established by nobody.

#### Scenario: Recording a combination shows its reach

- **WHEN** an operator records a combination of two or more types with a reason
- **THEN** it is stored, and the console shows the number of documents carrying
  every type of it

#### Scenario: A combination without a reason is refused

- **WHEN** an operator submits a combination with an empty reason
- **THEN** the console refuses it and says why, and nothing is stored

### Requirement: A browser always lands on a page that works

While the console is mounted, a request that asks for HTML SHALL end on a page,
never on an API error body: a refused request goes to the login page, the root
path goes to the console, and an unknown path goes to the console.

A lock that gives no indication where the key goes is not a lock, it is a wall.

A client that did not ask for HTML SHALL keep receiving the unchanged API error.
A 303 to an HTML form is the wrong answer for a program, which will try to parse
it and report something incomprehensible.

Without the console mounted there is no page to send anyone to, and every
response SHALL stay as it is. Redirecting to a route that answers 404 replaces
the wall with a circle.

#### Scenario: A browser refused on any path lands on the login page

- **WHEN** a request with an HTML `Accept` header is refused for a missing or
  invalid key, on any path
- **THEN** it is redirected to `/console/login`

#### Scenario: The bare hostname opens the console

- **WHEN** a browser requests `/`
- **THEN** it is redirected to the console

#### Scenario: An unknown path opens the console

- **WHEN** a browser requests a path that matches no route
- **THEN** it is redirected to the console

#### Scenario: An API client still gets an API error

- **WHEN** a request without an HTML `Accept` header is refused
- **THEN** it receives the unchanged 401 with the JSON body

### Requirement: The login form refuses a wrong key

The login form SHALL check the key against the configured set before storing it,
and SHALL redisplay the form with a reason when it does not match.

Storing an unchecked key produces a cookie that leads nowhere, so a typo becomes
the same dead end as no key at all — with the added confusion of having
apparently logged in.

#### Scenario: A wrong key is rejected at the form

- **WHEN** an operator submits a key that is not in the configured set
- **THEN** the form is shown again with a reason and no cookie is set

#### Scenario: Logging out clears the cookie

- **WHEN** an operator logs out
- **THEN** the cookie is cleared and the next console request goes to the login
  page
