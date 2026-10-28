# topic-labels-llm

## Why

Mark, 2026-10-28: *"the topics are meaningless to a human (ruil, https...);
that can occur a lot, but it doesn't make it an important topic. A language
model should be used for this, I think."* The review (docs/explanation/review-key-user-2026-10-28.md) measured names like
`onderdeel · verder · krijgen`: the three most distinctive TF-IDF terms, which
are frequent, not meaningful. An in-cluster model is available (Ollama,
`WORDSWORTH_LLM_MODEL`), and 407 of 415 documents already have a summary.

## What changes

- After a topic computation, each topic gets a **label** (at most six words)
  and a **one-line description**, written by the in-cluster language model
  from the summaries of the topic's most central documents (closest to the
  topic's centroid, at most eight) and its TF-IDF terms.
- The label is a model's claim, like a summary: stored with model and date,
  shown with that provenance, never in place of the TF-IDF terms (they stay as
  a subtitle).
- If the model is unreachable or answers with nothing usable, the topic keeps
  its TF-IDF name and the page says the label is missing. A computation never
  fails on the model.
- A name given by a person (`given_name`) still wins over both.
- Labelling runs on request, like the computation: `POST
  /dossiers/{id}/topics/labels`, and a button on the topics page.

## Out of scope

Changing how topics are computed (the clustering), and how many documents end
up in a topic. Labels for documents.
