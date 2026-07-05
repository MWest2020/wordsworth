# wordsworth

A sovereign pipeline that turns large volumes of (mostly Dutch) government
documents into a searchable, privacy-safe corpus:

**ingest → text extraction → anonymize/pseudonymize → store → index → hybrid search → rank**

What a consumer does with the documents afterwards is out of scope — wordsworth
is the engine. Reference case: Woo-request handling for a Dutch municipality.

## Principles

- Boring and auditable over fast or clever.
- No PII in the search index. Anonymization is irreversible; pseudonymization is
  controlled and reversible, and sits *before* indexing.
- Append-only, tamper-evident audit trail over every transformation, from day one.
- Local inference only — embeddings and any LLM run locally; no cloud APIs in the
  critical path.
- A failed embedding is a hard error, never a silent fallback.

## Status

Proof-of-concept, under construction. PoC scope: ingest + extraction +
anonymization, one corpus indexed and searchable via API with a closing audit
trail. Design and delta specs live under `openspec/`.

## Reused components

- [OpenAnonymiser](https://github.com/ConductionNL/openanonymiser_light) — anonymization adapter.
- [zeef](https://github.com/MWest2020/zeef) — ranking component (local Ollama embeddings, cosine).

## License

EUPL-1.2 — see [LICENSE](LICENSE).
