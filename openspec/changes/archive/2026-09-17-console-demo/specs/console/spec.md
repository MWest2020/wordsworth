## MODIFIED Requirements

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

## ADDED Requirements

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
