# Tasks

Build B, first of four. Every test runs against FakeTransit and the service's
own test database, under the fixture that makes `config.settings` raise. No
traffic from wordsworth.

- [x] First, settle `docs/reference/lock-order.md`: a section for the key
      service's database with the six rows of `design.md` "Locks" (4781,
      `known_documents`, `document_keys`, `pii_mappings`, 4783, 4782 last),
      which change takes which, and that wordsworth's "never together with
      4771" is about wordsworth's database. Proved by: the page diff.
- [x] Settings: `KEYSERVICE_OPENBAO_URL`, `KEYSERVICE_OPENBAO_TOKEN`,
      `KEYSERVICE_TRANSIT_KEK` (default `wordsworth`),
      `KEYSERVICE_KEY_CACHE_TTL` (300), `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS`
      (1 000). The service refuses to start with the URL or the token empty,
      and with the cap above 5 000, naming the setting. Proved by: one startup
      test per refusal, in the shape of `test_db_refuse.py`, and a test that
      differing `WORDSWORTH_*` values are ignored.
- [x] `create_app(transit_for=...)`: `None` builds the factory from the
      settings on first use; importing `serve.py` does no I/O. Proved by:
      `test_serve.py` still green, and a test that a passed `FakeTransit`
      factory is the one used.
- [x] `stores_pii.py`: mapping store and key vault over the service's models,
      `DurableKeyProvider` over them. Proved by: tests, and
      `tests/keyservice/test_no_config_import.py` still green.
- [x] `audit.py`: `append_access` under lock 4782 and `verify_access_chain`.
      Proved by: tests that the chain verifies after a run of appends and
      fails on a record altered behind the trigger's back.
- [x] `POST /v1/pseudonymise` as in `design.md`: tokens equal to what
      wordsworth's `Pseudonymizer` yields for the same value, type and domain;
      the response body (asserted whole, not per field) holds no value; an
      empty batch registers the document. Proved by: tests.
- [x] Type labels: a label outside `[A-Za-z0-9_]+` and a domain with `/` or
      empty → 422; a label wordsworth's `pii_categories` does not know is
      accepted. Proved by: tests.
- [x] Registry: each returned token is registered for that document with
      `source = minted`; re-pseudonymising adds and never removes; nothing
      else writes `document_tokens`. Proved by: tests.
- [x] `known_documents`: first call records the domain; another domain → 409;
      a tombstoned document (row written by the test) → 410. Proved by: tests.
- [x] The cap: refused above `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS` with 422 and
      nothing registered. Proved by: tests at the cap and cap + 1.
- [x] Transit down → 503 with nothing committed (no mapping, no registry row,
      no `known_documents` row, no audit record). Proved by: a test with a
      failing Transit.
- [x] One `access_audit` record per call, with counts and no value or token.
      Proved by: tests.
- [x] No route of this change returns a clear mapping value; no clear value
      or key byte in any log line. Proved by: a response scan and a
      log-capture test with sentinel values.
- [ ] The real artefact, from the side that holds no key: start the service
      against a reachable OpenBao (the homelab's, or `bao server -dev` with a
      Transit key), call `/v1/pseudonymise` with a service token, and see a
      token come back and a `key_vault` row wrapped under
      `KEYSERVICE_TRANSIT_KEK`. Proved by: the commands and their output in
      the PR. **Not done**: this builder's sandbox has no `bao`/`vault`
      binary and no reachable OpenBao (homelab or otherwise) -- see the run
      report.
- [x] Measurement at cutover (carried into `key-service-cutover`'s tasks): the
      time lock 4781 is held by a batch of the cap size against the real
      database, and the other writers' wait during it. Proved by: the figures
      in the cutover change's evidence. Nothing for this change to produce;
      the proof belongs to `key-service-cutover`'s own evidence.
- [x] ADR-0009: the guess-confirmation residual extended with the batch cap
      (no parallel row). Proved by: the ADR diff.
- [x] Docs: `POST /v1/pseudonymise` with its status codes and the cap in
      `docs/reference/key-service-api.md`; the settings with their defaults,
      which are required, and the startup refusals in
      `docs/how-to/key-service.md` (which stops saying "two environment
      variables"). Proved by: the docs check in CI.
