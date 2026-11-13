# Tasks

## 1. Labels
- [ ] `Generator.label(prompt) -> dict` on the protocol, `OllamaGenerator` and
      `DeterministicGenerator`; a transport failure or a non-JSON answer raises
      `GenerationError`. Proved by: unit tests of both drivers (Ollama against
      a fake HTTP transport, as the `summarise` tests do).
- [ ] `topic_labels.label_topic(session, index, topic_id, generator)`: the
      summaries of the topic's ≤8 most central documents plus its terms go to
      the model; a valid answer is stored with model and date. Proved by: a
      unit test with `InMemoryIndex` and a fake generator returning a valid
      label, asserting which eight documents' summaries were in the prompt.
- [ ] An invalid answer (seven words, empty, a pseudonym token with and
      without brackets, a URL, a two-line or over-long description) is
      rejected and the topic keeps what it had. Proved by: one test per case.
- [ ] `topic_labels.label_topics(session, index, dossier_id, generator)`
      labels every topic of the dossier and returns the counts; a generator
      that raises leaves every topic with its name and is counted as failed.
      Proved by: a test with a generator that raises on every call and one
      that raises on the second call only.
- [ ] An unreachable index labels nothing and is reported. Proved by: a test
      with an index whose `documents_in` raises `SearchUnavailable`: the call
      raises it, the generator was never called and no topic row changed.
- [ ] The four columns exist on a fresh database and are added to an existing
      one. Proved by: a test that runs `init_schema` on a database whose
      `topics` table lacks them.
- [ ] Display order: `given_name`, then `llm_label`, then the TF-IDF name; the
      TF-IDF terms shown as subtitle when a label is used. Proved by: a test of
      `display_name`.

## 2. Surfaces
- [ ] `python -m wordsworth.onderwerpen_labelen --dossier <name>` labels the
      topics without a label, `--opnieuw` all of them; one result line; exit
      code non-zero on a failed call, an unreachable index or an unknown
      dossier. Proved by: tests of `main()` with a fake generator for each of
      those outcomes, and one that a second run does not call the generator.
- [ ] `POST /topics/{topic_id}/label` labels one topic behind the gate of
      `PATCH /topics/{topic_id}`; 404 for an unknown topic; `labelled: false`
      with a reason for a rejected answer; 503 for an unreachable model or
      index. Proved by: API tests for each answer and for a caller without the
      right.
- [ ] No route labels a whole dossier. Proved by: a test that
      `POST /dossiers/{id}/topics/labels` answers 404 or 405.
- [ ] The topics page has a button per topic and shows label, description and
      "geschreven door <model> op <datum>"; a topic without a label says so.
      Proved by: console tests for a labelled and an unlabelled topic.

## 3. Docs
- [ ] `docs/how-to/topics.md`: labels, their provenance, the command and its
      result line, the one-topic route, what happens when the model or the
      index is down, the cost (about two minutes a topic), and that a
      recomputation drops the labels. Proved by: `grep -n
      "onderwerpen_labelen" docs/how-to/topics.md` finds the command.

## 4. Check
- [ ] `openspec validate topic-labels-llm --strict` passes.
- [ ] `uv run ruff check src/ tests/` is clean and the full suite passes;
      every new module is under 200 lines (`wc -l`). Proved by: the output in
      the PR, with the skipped tests listed.
- [ ] The PR states that label quality was not tested (no model where this is
      built) and that question M7 is settled at the rehearsal. Proved by: the
      PR text.
