## Why

Fase B needs a user-facing surface (API-first) to actually reveal PII under a
grant. The pieces exist — reversible per-type pseudonyms, selective
`deanonymize(allowed_types=...)`, and shareable/revocable grants — but nothing
ties them together over HTTP. Without an endpoint, key-gated reveal is a library
capability, not something a UI or client can drive.

## What Changes

- New endpoint `POST /documents/{document_id}/reveal` with body
  `{grant_id, types?}` returning `{document_id, revealed_text, revealed_types,
  withheld_types, grant_id}`. It reveals only the PII types the grant authorises;
  every other type stays pseudonymised. Omitting `types` reveals exactly what the
  grant allows.
- Status codes: 404 unknown document or unknown grant; 403 grant revoked/expired/
  scoped to another document; 409 document not yet de-identified; 200 otherwise.
- The reveal is audited by the existing `deanonymize` (actor = grant recipient,
  the revealed types, never any clear value).
- `create_app` gains optional `key_provider` and `grant_store`; the route is
  mounted only when both (plus `session_factory`) are present — the default
  deployment is unchanged until durable keys are wired in a later cycle.

## Capabilities

### Added Capabilities
- `reveal-api`: a key-gated, per-PII-type document reveal endpoint that enforces
  grants and audits every access.

## Impact

- Code: `api.py` (`RevealRequest`/`RevealResponse`, the conditional route, two new
  `create_app` params). Reuses `grants.authorize`, `pseudonymizer.deanonymize`,
  `pipeline.get_anonymized_text`, `mapping_store.PostgresMappingStore`. No schema
  change; no change to existing routes or the pipeline default.
- Tests: DB-integration (reveal reads stored pseudonyms + mappings and audits) run
  in CI.
- The durable/OpenBao-backed `key_provider` that lets the deployed app mount this
  route in production is a later cycle; this cycle proves the endpoint against a
  shared in-memory key provider.
