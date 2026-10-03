## MODIFIED Requirements

### Requirement: Zeef cosine is the final selector

The final ranking over the recall set SHALL NOT favour a document for being
short: on the Woo measurement collection of change `long-documents-rank-fairly`,
Recall@8 for the longest third of documents SHALL be at least Recall@8 for the
shortest third. No LLM scoring and no clustering SHALL influence the ranking.
The mechanism that meets this is recorded in that change's design, not here;
if no candidate meets it, this requirement is revised with the measurement,
not archived as if it held.

#### Scenario: Relevant document ranks first

- **WHEN** a hybrid search is run for a query strongly matching one document
- **THEN** that document is ranked first

#### Scenario: A long document that answers is among the sources

- **WHEN** `/ask` is asked "Welke afspraken zijn gemaakt over het windpark en
  de natuurcompensatie"
- **THEN** a document containing "windpark" is among the top 8 hybrid hits
