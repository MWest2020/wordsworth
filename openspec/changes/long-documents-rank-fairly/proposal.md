# Proposal: long documents rank fairly

## Why

`/ask` answered without sources, and measured on 2026-10-03 the cause is
retrieval, not generation. The question "Welke afspraken zijn gemaakt over het
windpark en de natuurcompensatie":

- **Not truncation:** the eight sources plus the instructions came to 3016
  tokens of a 4096 context.
- **Not the guard:** the model answered `{"answer": "", "citations": []}`,
  which its prompt tells it to do when the sources do not answer.
- **Retrieval:** none of the eight sources contains "windpark". Two documents
  in the corpus do. One reaches the hybrid recall set of 50, and the final
  ranking puts it **26th**. The top 20 are all short, 316-1524 characters;
  the windpark documents have a median length of 9600, the rest 1524.

The final selector is "zeef cosine" (spec `hybrid-search`): cosine between the
query and **one embedding per whole document**. A long document's single vector
stands for everything in it, so it sits further from any one question than a
short document that is vaguely about the same thing. The selector favours short
documents by construction, and an answer that lives in a long document does
not reach the model.

Nothing has measured ranking on real documents yet: the evaluation reference
says the IR metrics "need qrels and queries. Those do not exist for a Woo
corpus". So this change measures first, and changes the ranking only by what
the measurement shows.

## What Changes

- **A measurement collection from the real Woo corpus,** derived and not
  hand-judged (design, Decision 1):
  - one known-item query per document, built from its publisher-given file
    name, with that document as the relevant one;
  - one query per Woo decision, built from the decision's title, with the
    documents of that decision (recorded in `herkomst.jsonl`) as relevant.
- **A baseline:** the current ranking on that collection, with every metric
  also split by document length.
- **Two candidates, each measured on the same collection:**
  1. the final order by the fused RRF rank instead of cosine alone;
  2. passage embeddings: a document scored by its best passage, not by one
     vector for all of it.
- **The ranking that the measurement picks,** by the rule in the design, and
  the spec changed to state the property instead of the mechanism.

## Scope

**In:** the final ranking of hybrid search and so the sources of `/ask`,
`/hybrid` and the console search; the measurement collection and its script.

**Out:** the RRF recall stage itself, BM25 analysis, the generation prompt, and
a hand-judged collection, which needs a person and is noted as the next step if
the derived one cannot settle it.
