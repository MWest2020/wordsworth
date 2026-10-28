# Design: topic-labels-llm

## Decisions

- **Input is pseudonymised.** Summaries and terms come from the stored
  pseudonymised text; the model never sees clear values, and runs in-cluster.
- **Central documents, not all.** Eight summaries of the documents nearest the
  centroid describe a topic better than all of them and keep one call per
  topic (≈2 minutes each on this hardware, so 17 topics ≈ 35 minutes, on
  request).
- **Validation of the answer.** A label must be 1–6 words, no token
  placeholders (`[PERSOON 1]`), no URL; otherwise it is rejected and the
  fallback stays. A prompt asks for JSON `{label, description}` in Dutch.
- **Provenance.** New columns on `topics`: `llm_label`, `llm_description`,
  `llm_model`, `llm_at`. A recomputation replaces topics and so their labels.
