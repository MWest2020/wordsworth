## RENAMED Requirements

- FROM: `### Requirement: Zeef cosine is the final selector`
- TO: `### Requirement: The final ranking does not shut out long documents`

## MODIFIED Requirements

### Requirement: The final ranking does not shut out long documents

The final ranking over the recall set SHALL keep the fused RRF rank of the BM25
and kNN recall lists. It SHALL NOT re-sort them by cosine against one embedding
per whole document: on the Woo measurement collection of change
`long-documents-rank-fairly` that re-sort found not one of the longest third of
documents by its own title (Recall@8 0.000). With the fused rank, Recall@8 SHALL
be above zero in every length third, and every change to ranking SHALL record
the values per third on that collection. No LLM scoring and no clustering SHALL
influence the ranking.

Known limitation, measured 2026-10-05 on the full index and accepted by Mark the
same day: the longest third is still found less often than the shortest
(Recall@8 0.400 against 0.731). Ranking by best passage closed the gap but
flipped the bias, filling the top 8 with long documents and missing the
windpark question; that variant is not the default.

#### Scenario: Relevant document ranks first

- **WHEN** a hybrid search is run for a query strongly matching one document
- **THEN** that document is ranked first

#### Scenario: A long document that answers is among the sources

- **WHEN** `/ask` is asked "Welke afspraken zijn gemaakt over het windpark en
  de natuurcompensatie"
- **THEN** a document containing "windpark" is among the top 8 hybrid hits

#### Scenario: No length third is shut out

- **WHEN** the ranking is measured on the Woo collection
- **THEN** Recall@8 is above zero for the short, middle and long third alike
