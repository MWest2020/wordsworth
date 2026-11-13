# topic-labels-llm

## Why

Mark, 2026-10-28: *"the topics are meaningless to a human (ruil, https...);
that can occur a lot, but it doesn't make it an important topic. A language
model should be used for this, I think."* The review (docs/explanation/review-key-user-2026-10-28.md) measured names like
`onderdeel · verder · krijgen`: the three most distinctive TF-IDF terms, which
are frequent, not meaningful. An in-cluster model is available (Ollama,
`WORDSWORTH_LLM_MODEL`), and 407 of 415 documents already have a summary.

## What changes

- Each topic can get a **label** (at most six words) and a **one-line
  description**, written by the in-cluster language model from the summaries
  of the topic's most central documents (closest to the topic's centroid, at
  most eight) and its TF-IDF terms.
- The label is a model's claim, like a summary: stored with model and date,
  shown with that provenance, never in place of the TF-IDF terms (they stay as
  a subtitle).
- **Labelling a whole dossier is a command**,
  `python -m wordsworth.onderwerpen_labelen --dossier <name>`, like
  `python -m wordsworth.samenvatten`. One label takes about two minutes on the
  cluster's hardware, so the 17 topics of the Gooise Meren dossier take about
  35 minutes: that does not fit in an HTTP request, which is the reason
  summaries moved to a command (`samenvatten-als-commando`).
- **The API and the console label one topic per call**:
  `POST /topics/{topic_id}/label`, and a button per topic on the topics page.
  The button does not wait for the model: it starts the work, the page comes
  back saying "bezig, ververs over ongeveer 2 minuten", and the server
  finishes and stores the label. A two-minute request would be cut by
  Cloudflare (100 seconds) and by oauth2-proxy (30 seconds by default).
- If the model is unreachable or answers with nothing usable, the topic keeps
  its TF-IDF name, the answer says so, and the page says the label is missing.
  If the search index is unreachable, nothing is labelled and the answer says
  that too: topic membership lives only in the index. A topic computation
  never calls the model and never fails on it.
- A name given by a person (`given_name`) still wins over both.

## Amended 2026-11-13

The first version put the whole dossier in one request
(`POST /dossiers/{id}/topics/labels`). That route is removed from this change
before it was built. Also corrected against the code: the labelling function
takes the search index (membership and vectors are not in Postgres), the
generator protocol gets a named method, and the logic goes in new modules
because `topics.py`, `api.py` and `models.py` are already over 200 lines.

## Working assumptions (Mark can overrule)

- **Dossier-wide labelling is a command, not a request.** Decided in the
  product plan as a working assumption: 35 minutes does not fit a request.
- **Label quality is not tested by this change (question M7).** The labels
  come from `llama3.2:3b`; how good six Dutch words from that model are cannot
  be tested where this is built (no Ollama there). Default: the command runs
  at the demo rehearsal, Mark reads the 17 labels once, and a bad one gets a
  `given_name`, which wins. The tests in this change prove the plumbing and
  the validation, not the quality.

## Out of scope

Changing how topics are computed (the clustering), and how many documents end
up in a topic. Labels for documents. A queue or background worker for
labelling.
