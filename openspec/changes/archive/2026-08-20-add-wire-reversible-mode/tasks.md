## 1. Config + composition

- [x] 1.1 `settings.reversible_mode` (`WORDSWORTH_REVERSIBLE`, default false).
- [x] 1.2 `create_app` gains `anonymizer_factory`/`key_provider_factory`/
  `grant_store_factory`; ingest + reveal resolve session-scoped backends per
  request (factory wins over singleton); reveal mounts on singleton-or-factory.
- [x] 1.3 `serve._reversible_wiring` composes a shared `OpenBaoTransit` + per-request
  durable-key/mapping/grant factories; off ⇒ unchanged irreversible default.

## 2. Gate

- [x] 2.1 Local tests: flag default off; reveal route absent by default and present
  with factories; `build_app` flips by config with no network I/O at import.
- [x] 2.2 DB-integration (CI): ingest→reveal end-to-end through the factories;
  durability across requests (shared vault + FakeTransit); only granted type revealed.
- [x] 2.3 Full suite green in CI + `openspec validate`.
