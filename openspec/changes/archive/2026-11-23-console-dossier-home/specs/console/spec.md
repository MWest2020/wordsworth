## ADDED Requirements

### Requirement: The console starts on a dossier

The console home SHALL let the reader choose a dossier, showing for each its
number of live documents and topics, and SHALL open that dossier directly when
the installation has exactly one. The dossier page SHALL offer a question box
that searches that dossier, the dossier's topics with a link that searches within
each, and its live documents. Deleted and superseded documents SHALL be hidden as
the hidden-documents rule of the console requires.

#### Scenario: One dossier opens directly

- **WHEN** an operator opens `/console` on an installation with one dossier
- **THEN** they land on that dossier's page

#### Scenario: The dossier page offers the three ways in

- **WHEN** an operator opens a dossier page
- **THEN** it shows a question box scoped to the dossier, its topics with search-within links, and only its live documents

#### Scenario: An unknown dossier is named

- **WHEN** an operator opens `/console/dossier?dossier=<name>` for a name that does not exist
- **THEN** the answer is 404 and lists the dossiers that do

#### Scenario: A dossier name is free text

- **WHEN** an operator opens the page of a dossier whose name contains a slash or a space
- **THEN** that dossier's page is shown, because the dossier is addressed by the `dossier` query parameter
