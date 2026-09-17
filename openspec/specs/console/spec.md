# console Specification

## Purpose
TBD - created by archiving change document-console. Update Purpose after archive.

## Requirements

### Requirement: The console shows the artefact, never the original

The console SHALL render the text the pipeline produced after pseudonymisation,
with its tokens marked and typed.

It MAY show original values only as the result of the existing grant-gated,
audited reveal endpoint, called with the viewer's own credentials. It SHALL NOT
implement authorisation, key handling or audit of its own for that purpose, and
SHALL present a refusal as a refusal rather than hiding the option that produced
it.

The original concern stands and was stated too broadly. What is wrong is a
console with its OWN way out — its own checks, its own keys, its own route past
the grant. What is not wrong is a person using the same audited door with a
screen instead of `curl`. A refusal shown on screen is the demonstration, not a
failure of it: a department that does not hold the key does not get it from a
prettier page either.

#### Scenario: A document page shows pseudonymised text

- **WHEN** an operator opens a document in the console
- **THEN** the page shows the stored pseudonymised text with each token marked
  and labelled by type, and no original value until a reveal is performed

#### Scenario: A reveal goes through the one door

- **WHEN** an operator reveals from the console
- **THEN** the request reaches the existing reveal endpoint with the operator's
  own credentials, and the same audit record is written as for any other caller

#### Scenario: A refused reveal is shown, not hidden

- **WHEN** the grant does not authorise the caller or the requested types
- **THEN** the page reports the refusal and the text stays pseudonymised

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

### Requirement: The console carries its own assets

The console SHALL serve its fonts and stylesheet from its own origin and SHALL
NOT reference a third-party CDN.

This screen is where wordsworth's claim to sovereignty is demonstrated, and it is
also the screen people inspect. A page that fetches its letters from Google
refutes that claim in the network inspector, whatever the surrounding text says.

The asset subtree SHALL be reachable without a key, because the login page is
itself reachable without a key and a login screen rendered without its letters is
a broken door. The exemption SHALL cover that subtree only.

#### Scenario: No third-party origin appears in a rendered page

- **WHEN** any console page is rendered
- **THEN** it references no font or stylesheet host other than the console's own

#### Scenario: The stylesheet and the file it points at are both served

- **WHEN** the stylesheet is requested and a font URL inside it is followed
- **THEN** both are served, so a packaging regression that ships the CSS without
  the font files is caught

#### Scenario: The exemption is a subtree, not a blanket

- **WHEN** a path outside the asset subtree is requested without a key
- **THEN** it is refused as before

### Requirement: The corpus can be searched from the console

The console SHALL offer a search over the corpus that reports, per hit, its
ranking score and a fragment of the PSEUDONYMISED text, and SHALL offer example
terms to start from.

Searching the pseudonymised index is the claim this project rests on — that
protecting the text does not destroy its usefulness. A claim demonstrated on
invented data is an illustration; the same screen over the real corpus is
evidence.

A fragment SHALL be taken from the stored pseudonymised text, never from a
source document.

#### Scenario: A search reports scores and fragments

- **WHEN** an operator searches for a term
- **THEN** each hit shows its score and a fragment of the pseudonymised text,
  and links to that document

#### Scenario: Example terms are offered as examples

- **WHEN** the search page is shown
- **THEN** it offers terms to start from and does not promise they match, and a
  term with no hits reports that plainly

### Requirement: A document's reveal history is visible without its values

The console SHALL show, for a document, the reveals recorded against it: when,
by whom, under which grant and which types. It SHALL NOT show any revealed
value.

An audit trail nobody looks at is a promise, not a control. Putting it on the
same page as the reveal button is what makes it one.

#### Scenario: The trail names types and never values

- **WHEN** a document's reveal history is shown
- **THEN** each entry names the caller, the grant and the types, and contains no
  PII value
