---
status: current
last_reviewed: 2026-10-28
---

# Review: the console through a key user's eyes (2026-10-28)

Mark, 2026-10-28: *"The key user wants to find topics quickly, ask targeted
questions, know which documents are relevant, and share with layered
anonymisation. From that thought, review the app; then write spec and
implement."* And: *"the topics are meaningless to a human"*, *"I still only see
the deleted files (a key user doesn't care)"*.

Read on the live installation (homelab), dossier *Gooise Meren
Woo-publicatie 2022*, through the console routes with an API key and the code
behind them. Counts only; no document content.

## The state of the corpus

| Fact | Count |
|---|---|
| live documents in the dossier | 415 (408 in the search index) |
| documents with a summary | 407, all from one generator |
| documents with passage vectors | 408 |
| topics | 17, with 184 documents in one; 0 named by a person |
| deleted documents (rows kept) | 215 |
| active grants | 405, all for one recipient |

## The four jobs

### 1. Find topics quickly

- **Works:** topics exist per dossier (`/console/topics`), and a topic narrows a
  search (`topic=` on `/console/search`).
- **Missing:** a name a person understands. Names are the three most
  distinctive TF-IDF terms (`topics.py`, docs/how-to/topics.md, "Namen");
  measured ones read like `onderdeel · verder · krijgen` and
  `bezoekadres · https · vriendelijke`. Frequent is not important. An in-cluster
  language model is available (Ollama, `WORDSWORTH_LLM_MODEL`), and every
  document already has a summary, so a topic can be labelled from its most
  central documents' summaries at little cost.
- **Missing:** 224 of 408 documents are in no topic. A key user doesn't see
  that the topic list covers less than half the dossier.
- **Confusing:** topics vanished from the index after a reprocess (fixed by
  hand, structural fix queued as `reindex-keeps-topics`).

### 2. Ask a targeted question

- **Works:** the search page asks for a dossier first and ranks with the
  question embedded (`console_search.py:_rank`, "semantisch + lexicaal"); three
  six-word questions each returned 10 documents.
- **Missing:** the home page is not where a key user starts. `/console`
  (`console.py:index`) lists the 200 most recently touched documents, and on
  this installation all 200 are deleted ones. The page offers no dossier, no
  topics and no question box. Hiding deleted rows is queued
  (`console-hide-deleted`); a dossier-first home is not.

### 3. Know which documents are relevant

- **Works:** a score and a summary per hit, the summary marked as a model's
  claim (`templates/search.html`).
- **Missing:** *why* a document matched. The fragment is cut around the first
  query word found in the text (`console_data.fragment`); a semantic match
  without a shared word falls back to the first 180 characters, usually a
  letterhead or mail header. The passage that ranked the document is known to
  the index (408 documents carry passage vectors), but the index stores only
  vectors, no positions, so the console can't show it.
- **Confusing:** the score is a fused rank value (RRF, then cosine). Shown bare,
  it invites comparisons it doesn't support.

### 4. Share with layered anonymisation

- **Works:** grants by PPL or role, reveal with audit, a reveal button on the
  document page, and a redacted PDF through the API (`/documents/{id}/redacted.pdf`)
  for 354 of 415 documents.
- **Missing:** a way to share from the console. The console can't issue a grant
  (document page: "De console mag er zelf geen uitgeven"), so sharing means the
  API or the CLI. The redacted PDF and the reveal PDF are not linked from the
  console at all (docs/how-to/pdf-redaction.md: "undecided").
- **Missing:** sharing a set: grants are per document, so a dossier or a topic
  takes one grant per document (405 for Mark's).

## What follows

In order of value to the key user, each one factory build, after the two
already queued (`console-hide-deleted`, `reindex-keeps-topics`):

1. `console-dossier-home`: the console opens on a dossier: its topics, a
   question box and its documents; no deleted rows.
2. `topic-labels-llm`: a readable label and a one-line description per topic,
   written by the in-cluster model from the topic's most central documents,
   marked as a model's claim, with the TF-IDF name as fallback and subtitle.
3. `search-matching-passage`: the index keeps where each passage sits, the
   ranking says which passage won, and the result shows that passage with the
   query terms marked and a plain-language reason instead of a bare score.
4. `console-pdf-views`: the document page links the redacted PDF and offers
   the reveal PDF next to the text reveal.
5. `console-share`: share a document, a topic or a dossier with a recipient at
   a PPL (or a role), with an expiry; the console issues the grants through the
   same issuer gate as the API and shows the links to send.
