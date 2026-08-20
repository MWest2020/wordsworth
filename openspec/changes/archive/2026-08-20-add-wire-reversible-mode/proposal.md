## Why

The reversible-pseudonymisation stack (per-type keyed tokens, durable OpenBao-
wrapped keys, grants, the reveal endpoint) was built and CI-proven cycle by
cycle, but it was all dormant: the deployed straat still ran the irreversible
`OpenAnonymiserAnonymizer` and mounted no reveal route. This wires reversible mode
into the composition root so an operator can turn it on — without changing the
default behaviour until they do.

## What Changes

- Config flag `WORDSWORTH_REVERSIBLE` (default **false**).
- `create_app` gains optional per-request factories `anonymizer_factory`,
  `key_provider_factory`, `grant_store_factory` (`Callable[[Session], X]`), so the
  session-scoped Postgres/OpenBao-backed backends are built fresh per request; the
  existing singleton params stay for tests/session-free doubles, and a factory
  wins over its singleton. The reveal route now mounts when a key provider AND a
  grant store are available *by singleton or factory*.
- `serve.build_app`: when `reversible_mode` is on, compose a shared `OpenBaoTransit`
  client and per-request factories — `ReversibleAnonymizer` over a
  `DurableKeyProvider(PostgresKeyVaultStore(session), transit)` + `PostgresMappingStore(session)`
  for ingest, the same durable provider for reveal, and `PostgresGrantStore(session)`.
  When off, behaviour is byte-for-byte as before (irreversible driver, no reveal).
- No OpenBao I/O at import: factories are only invoked per request, so the pod
  boots even when OpenBao is briefly sealed.

## Capabilities

### Modified Capabilities
- `deployment`: reversible pseudonymisation + the reveal route are selectable by
  config, default off; when on, the pipeline emits durable keyed pseudonyms and
  the index still holds only pseudonyms.

## Impact

- Code: `config.py` (`reversible_mode`), `api.py` (three factory params, per-request
  resolution in ingest + reveal), `serve.py` (`_reversible_wiring`).
- Tests: pure/local (flag default off; reveal route mounts only with factories;
  `build_app` flips by config with no network) + DB-integration in CI (ingest →
  reveal end-to-end through the factories, durability across requests via a shared
  vault + FakeTransit).
- Go-live against a real OpenBao (deploy + init/unseal + Transit KEK) is a separate
  infra step; this cycle is the code path that makes it switch-on-able.
