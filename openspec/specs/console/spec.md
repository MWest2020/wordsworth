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
