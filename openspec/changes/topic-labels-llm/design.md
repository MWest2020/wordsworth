# Design: topic-labels-llm

## Decisions

- **Input is pseudonymised.** Summaries and terms come from the stored
  pseudonymised text; the model never sees clear values, and runs in-cluster.
- **The function takes the index.**
  `topic_labels.label_topics(session, index, dossier_id, generator)` and
  `topic_labels.label_topic(session, index, topic_id, generator)`. Which
  documents are in a topic, and their vectors, exist only in the search index
  (`models.Topic` holds the description only; `topics.compute` reads
  `index.documents_in`). A `SearchUnavailable` from that read is not caught
  in `topic_labels.py`: nothing is labelled, every stored name and label stays
  as it was, and the caller reports it. The command prints it and exits
  non-zero. The route catches it itself and answers 503 with a detail that
  names the index; `api.py` has no general mapping of `SearchUnavailable` to
  a status today (only the console catches it), so this mapping is new and
  lives in the new router.
- **Central documents, not all.** Per topic: its members from
  `index.documents_in(dossier)`, the centroid of their vectors, the eight
  members nearest the centroid, their stored summaries
  (`summaries.by_document`) and the topic's TF-IDF terms. One model call per
  topic. A topic whose central documents have no summary at all is not
  labelled and the model is not called: the result counts it under
  `no_summaries`, and the route answers `labelled: false` with the reason
  `no_summaries`.
- **A named method on the generator protocol.** `Generator.label(prompt) ->
  dict`, on the protocol, on `OllamaGenerator` (asks for JSON
  `{label, description}` in Dutch) and on `DeterministicGenerator` (a fixed
  answer built from the prompt, for tests and the local demo). A transport
  failure or an answer that is not JSON raises `GenerationError`, as
  `summarise` does.
- **Validation of the answer.** A label must be 1–6 words and contain no
  pseudonym token (`[LABEL:hash]`, also without its brackets), no bracketed
  placeholder of the shape `\[[A-Z_]+\]` (`[PERSOON]`, `[NAAM]`: what a model
  writes when it imitates a token), and no URL; the description must be one
  line of at most 200 characters under the same three rules. Anything else is
  rejected, not repaired: the topic keeps what it had and the result counts
  one rejection.
- **Provenance.** Four nullable columns on `topics`: `llm_label`,
  `llm_description`, `llm_model`, `llm_at`. They are declared on
  `models.Topic` and added to `db._COLUMNS`, the list `init_schema` migrates
  an existing database from. A recomputation replaces the topics and so their
  labels; the topics page then says the labels are missing and names the
  command.
- **The command.** `python -m wordsworth.onderwerpen_labelen --dossier <name>`
  labels the topics of that dossier that have no label yet; `--opnieuw` labels
  all of them again. It prints one line with the number of topics `seen`,
  `labelled`, `rejected`, `no_summaries`, `skipped` (had a label already) and
  `failed` (the model call raised), and exits non-zero when a model call
  failed or the index was unreachable. An unknown dossier name exits non-zero.
  `--dossier` takes the dossier's **name** on purpose, as the console does;
  `wordsworth.samenvatten --dossier` takes a UUID, and this command does not
  copy that: an operator at the rehearsal knows the name, not the id.
- **One topic per request, behind the corpus gate.**
  `POST /topics/{topic_id}/label` calls `_guard_corpus_read`, the gate the
  summaries sit behind: a label is written from summaries, and
  `PATCH /topics/{topic_id}` has no gate of its own beyond the API key to
  borrow. The route runs the model call in the request and answers with the
  stored label, description, model and date; with `labelled: false` and the
  reason (`rejected` or `no_summaries`); 404 for an unknown topic; and 503,
  naming which, when the model (`GenerationError`) or the index
  (`SearchUnavailable`) is unreachable. It is for callers inside the cluster:
  one call is about two minutes of model time.
- **The console button does not wait.** A browser reaches the console through
  Cloudflare, which cuts a request at 100 seconds, and oauth2-proxy, whose
  upstream timeout is 30 seconds by default; a two-minute label call would be
  cut by both. So the button's `POST` (behind the console's read gate, as the
  other topic actions) hands the same `label_topic` call to a background task
  of the request and returns the topics page at once with "bezig, ververs
  over ongeveer 2 minuten". The server finishes and stores the label; after a
  reload the page shows it, or still says the label is missing. The outcome
  of the background call is one log line (`topic id`, and `labelled`,
  `rejected`, `no_summaries` or `failed`; never the label text of a rejected
  answer). One labelling runs at a time (`concurrency.limiter`); a click
  while one runs answers "er loopt al een label-opdracht" and starts nothing.
  The limit is per process (one semaphore per worker); two pods or workers
  can each run one. The route takes the same slot without waiting and
  answers 409 "er loopt al een label-opdracht" when it is taken.
  No queue and no worker: if the process restarts mid-call the label is not
  stored and the button can be pressed again.
- **Display.** `topics.display_name`: `given_name`, then `llm_label`, then
  `computed_name`. Where a label is shown, the description, "geschreven door
  <model> op <datum>" and the TF-IDF terms as subtitle are shown with it.

## Where the code goes

`topics.py` (431 lines), `api.py` (1996) and `models.py` (401) are over the
200-line limit already, so they change only at the call sites named here.

- new `topic_labels.py`: selection of central documents, prompt, validation,
  storing;
- new `topic_labels_api.py`: a router with the one route, included from
  `api.py` in one line;
- new `onderwerpen_labelen.py`: the command;
- `generator.py` (153 lines): `label` on the protocol and both drivers. If
  that takes it over 200, the label prompt and the JSON parsing go in
  `topic_labels.py` and the drivers keep a thin method;
- `topics.py`: `display_name` only;
- `models.py`: the four columns on `Topic`;
- `db.py` (201 lines, already one over): four entries in `_COLUMNS`, nothing
  else;
- `console_topics.py`, `templates/topics.html`: the button and the label.

## Rejected

- **One request for the whole dossier** (the first version of this change): 35
  minutes inside a `POST`.
- **Labelling as part of the topic computation.** A computation would then
  depend on the model; today it never does.

## Rejected, for the button

- **A button that waits for the answer**: cut at 30 or 100 seconds, after
  which the browser shows an error for work that then succeeds.
- **Raising the proxy timeouts**: Cloudflare's limit is not ours to raise, and
  the homelab repo is outside this change.
