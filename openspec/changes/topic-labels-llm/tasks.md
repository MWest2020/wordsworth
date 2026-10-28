# Tasks

## 1. Labels
- [ ] `topics.label_topics(session, dossier_id, llm)`: per topic, the summaries of
      its ≤8 most central documents plus its terms go to the model; a valid
      answer is stored with model and date. Proved by: a unit test with a fake
      model returning a valid label.
- [ ] An invalid answer (too long, a token placeholder, a URL, not JSON) is
      rejected and the TF-IDF name stays. Proved by: one test per case.
- [ ] An unreachable model leaves every topic with its TF-IDF name and reports
      how many were labelled. Proved by: a test with a model that raises.
- [ ] Display order: `given_name`, then `llm_label`, then the TF-IDF name; the
      TF-IDF terms shown as subtitle when a label is used. Proved by: a test of
      `display_name`.
## 2. Surfaces
- [ ] `POST /dossiers/{id}/topics/labels` and a console button; the topics page
      shows label, description and "geschreven door <model> op <datum>".
      Proved by: API and console tests.
## 3. Docs
- [ ] `docs/how-to/topics.md`: labels, their provenance, the fallback, the cost.
