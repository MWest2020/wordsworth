# Design: topic-labels-llm

## Decisions

- **Input is pseudonymised.** Summaries and terms come from the stored
  pseudonymised text; the model never sees clear values, and runs in-cluster.
- **The function takes the index.**
  `topic_labels.label_topics(session, index, dossier_id, generator)` and
  `topic_labels.label_topic(session, index, topic_id, generator)`. Which
  documents are in a topic, and their vectors, exist only in the search index
  (`models.Topic` holds the description only; `topics.compute` reads
  `index.documents_in`). A `SearchUnavailable` from that read is not caught:
  nothing is labelled, every stored name and label stays as it was, and the
  caller reports it (the command prints it and exits non-zero; the API answers
  503 as the other index outages do).
- **Central documents, not all.** Per topic: its members from
  `index.documents_in(dossier)`, the centroid of their vectors, the eight
  members nearest the centroid, their stored summaries
  (`summaries.by_document`) and the topic's TF-IDF terms. One model call per
  topic. A topic whose central documents have no summary at all is not
  labelled and is counted as such.
- **A named method on the generator protocol.** `Generator.label(prompt) ->
  dict`, on the protocol, on `OllamaGenerator` (asks for JSON
  `{label, description}` in Dutch) and on `DeterministicGenerator` (a fixed
  answer built from the prompt, for tests and the local demo). A transport
  failure or an answer that is not JSON raises `GenerationError`, as
  `summarise` does.
- **Validation of the answer.** A label must be 1–6 words and contain no
  pseudonym token (`[LABEL:hash]`, also without its brackets) and no URL; the
  description must be one line of at most 200 characters with no token and no
  URL. Anything else is rejected, not repaired: the topic keeps what it had
  and the result counts one rejection.
- **Provenance.** Four nullable columns on `topics`: `llm_label`,
  `llm_description`, `llm_model`, `llm_at`. They are declared on
  `models.Topic` and added to `db._COLUMNS`, the list `init_schema` migrates
  an existing database from. A recomputation replaces the topics and so their
  labels; the topics page then says the labels are missing and names the
  command.
- **The command.** `python -m wordsworth.onderwerpen_labelen --dossier <name>`
  labels the topics of that dossier that have no label yet; `--opnieuw` labels
  all of them again. It prints one line with the number of topics seen,
  labelled, rejected, skipped and failed, and exits non-zero when a model call
  failed or the index was unreachable. An unknown dossier name exits non-zero.
- **One topic per request.** `POST /topics/{topic_id}/label` behind the same
  gate as `PATCH /topics/{topic_id}`. It answers with the stored label,
  description, model and date; with `labelled: false` and the reason when the
  answer was rejected; and with 503 when the model or the index is
  unreachable. One call is about two minutes of model time.
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
- `generator.py`: `label` on the protocol and both drivers;
- `topics.py`: `display_name` only;
- `models.py` and `db.py`: the four columns;
- `console_topics.py`, `templates/topics.html`: the button and the label.

## Rejected

- **One request for the whole dossier** (the first version of this change): 35
  minutes inside a `POST`.
- **Labelling as part of the topic computation.** A computation would then
  depend on the model; today it never does.

## Risk

One label is about two minutes and the console button waits for it. Whether
the ingress keeps a request open that long is not checked here; the rehearsal
checks it. If it cuts the request, the label is still stored and the page
shows it on reload, and the command remains the way to label.
