# key-service-originals

## Why

ADR-0009, build B, second of four (the split of `key-service-vault`, see
`key-service-pseudonymise`). The service seals originals for storage and
opens them for processing, so that wordsworth never holds a data key or a
KEK. This change carries the seal and open half of the vault: the service's
own document-key store, `seal`, and `open` with its purposes and its two
failure modes. The rate limit on `open` follows in `key-service-open-limits`;
until the cutover no caller reaches the service.

## What changes

- The service's document-key store over its own `DocumentKeyRecord`
  (`doc_keys.py`): mint, unwrap, evict and the unwrap cache, reimplemented,
  not wordsworth's `DocumentKeys`.
- `POST /v1/originals/{document_id}/seal`: bytes in, sealed bytes and
  `X-Key-Id` out; one key per object key, never a second one.
- `POST /v1/originals/{document_id}/open`: sealed bytes in, plaintext out,
  for a purpose from a fixed list; audited; a tampered key or envelope fails
  closed and is audited, an unreachable Transit is a 503.
- Settings: `KEYSERVICE_ORIGINALS_KEK`, `KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN`,
  `KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE`, `KEYSERVICE_MAX_ORIGINAL_BYTES`.
- ADR-0009: a risk line that `open` returns, and `seal` receives, plaintext
  over HTTP on the wordsworth-to-service link.
- Docs: both endpoints in `docs/reference/key-service-api.md`, the settings
  and the wire in `docs/how-to/key-service.md`.

- Amendment after the reviewer's FAIL on wordsworth#544 (`api_originals.py`
  at 202 lines, over the 200-line invariant): seal stays in
  `api_originals.py`, open lives in `api_open.py`, with the line-limit check
  as a task; the real-artefact smoke (seal and open against the OpenBao of
  the pseudonymise smoke run) is required PR evidence.

No wordsworth module changes: the service has its own `kek_for(domain)` over
its own settings, so `document_keys.kek_name_for` and `DocumentKeys` keep
their signatures.

## Out of scope

The rate limit, the 429 audit, `service_state` and `/v1/metrics`
(`key-service-open-limits`); destroying keys (`key-service-delete`); which of
`put_original`'s rules wordsworth keeps after the switch
(`key-service-cutover`, `originals-ingest-switch`).

## Next

`key-service-open-limits`

## Depends on

`key-service-pseudonymise` (settings and the Transit seam, the known-documents
table, the audit writer, the lock order).
