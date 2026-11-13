# Tasks

## 1. Labels
- [x] `Generator.label(prompt) -> dict` on the protocol, `OllamaGenerator` and
      `DeterministicGenerator`; a transport failure or a non-JSON answer raises
      `GenerationError`. Proved by: unit tests of both drivers (Ollama against
      a fake HTTP transport, as the `summarise` tests do).
- [x] `topic_labels.label_topic(session, index, topic_id, generator)`: the
      summaries of the topic's ≤8 most central documents plus its terms go to
      the model; a valid answer is stored with model and date. Proved by: a
      unit test with `InMemoryIndex` and a fake generator returning a valid
      label, asserting which eight documents' summaries were in the prompt.
- [x] An invalid answer (seven words, empty, a pseudonym token with and
      without brackets, a bracketed placeholder such as `[PERSOON]`, a URL, a
      two-line or over-long description) is rejected and the topic keeps what
      it had. Proved by: one test per case.
- [x] A topic whose central documents have no summary is not sent to the
      model and is counted under `no_summaries`. Proved by: a test asserting
      the generator was not called and the count.
- [x] `topic_labels.label_topics(session, index, dossier_id, generator)`
      labels every topic of the dossier and returns the counts; a generator
      that raises leaves every topic with its name and is counted as failed.
      Proved by: a test with a generator that raises on every call and one
      that raises on the second call only.
- [x] An unreachable index labels nothing and is reported. Proved by: a test
      with an index whose `documents_in` raises `SearchUnavailable`: the call
      raises it, the generator was never called and no topic row changed.
- [x] The four columns exist on a fresh database and are added to an existing
      one. Proved by: a test that runs `init_schema` on a database whose
      `topics` table lacks them.
- [x] Display order: `given_name`, then `llm_label`, then the TF-IDF name; the
      TF-IDF terms shown as subtitle when a label is used. Proved by: a test of
      `display_name`.

## 2. Surfaces
- [x] `python -m wordsworth.onderwerpen_labelen --dossier <name>` labels the
      topics without a label, `--opnieuw` all of them; one result line; exit
      code non-zero on a failed call, an unreachable index or an unknown
      dossier. Proved by: tests of `main()` with a fake generator for each of
      those outcomes, and one that a second run does not call the generator.
- [x] `POST /topics/{topic_id}/label` labels one topic behind
      `_guard_corpus_read`; 404 for an unknown topic; `labelled: false` with
      the reason `rejected` or `no_summaries`; 503 naming the model or the
      index when one is unreachable. Proved by: API tests for each answer, and
      one with a caller whose label is not in the corpus read labels: 403 and
      the generator was not called.
- [x] No route labels a whole dossier. Proved by: a test that
      `POST /dossiers/{id}/topics/labels` answers 404 or 405.
- [x] The topics page has a button per topic and shows label, description and
      "geschreven door <model> op <datum>"; a topic without a label says so.
      Proved by: console tests for a labelled and an unlabelled topic.
- [x] The button does not wait for the model: its `POST` returns the page with
      "bezig, ververs over ongeveer 2 minuten" before the generator has
      answered, and the label is stored when it has. Proved by: a console test
      with a generator that blocks on an event: the response arrives while it
      blocks, and after the event is set the topic row holds the label.
- [x] A second click while a labelling runs starts nothing and says so; the
      background outcome is logged without the text of a rejected label.
      Proved by: a test with the blocking generator (one call counted), and a
      test on the captured log for a rejected answer.

## 3. Docs
- [x] `docs/how-to/topics.md`: labels, their provenance, the command and its
      result line, the one-topic route, what happens when the model or the
      index is down, the cost (about two minutes a topic), that the button
      does not wait and why (the 30 and 100 second limits), where the outcome
      of a button press is logged, and that a recomputation drops the labels.
      Proved by: `grep -n
      "onderwerpen_labelen" docs/how-to/topics.md` finds the command.

## 4. Check
- [x] `openspec validate topic-labels-llm --strict` passes.
- [x] `uv run ruff check src/ tests/` is clean and the full suite passes;
      every new module and `generator.py` are under 200 lines and `db.py`
      grew by the four `_COLUMNS` entries only (`wc -l`, `git diff --stat`).
      Proved by: the output in the PR, with the skipped tests listed.
- [x] The PR states that label quality was not tested (no model where this is
      built) and that question M7 is settled at the rehearsal. Proved by: the
      PR text.
