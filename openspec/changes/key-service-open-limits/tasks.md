# Tasks

Build B, third of four. Every test runs against FakeTransit and the service's
own test database, under the fixture that makes `config.settings` raise. No
traffic from wordsworth.

- [ ] `service_state` as in `design.md` (`kind`, `key`, `counter`, `data`,
      `updated_at`; PK `kind`, `key`), written only by `state.py`; the
      service's `RateLimitBucket` model is removed and its pair leaves
      `_COPIED_PAIRS`. Proved by: `tests/keyservice/test_drift.py` green
      without that pair, and the init test listing exactly the service's
      tables including `service_state` and without `rate_limit_buckets`.
- [ ] `tests/keyservice/test_service_state_drift.py`: the columns of
      `service_state`, every table classified (copied or own), no counter or
      window column elsewhere, absent from wordsworth's metadata, and
      `state.py` never names `access_audit`. Proved by: that test, and a
      mutation (an extra column on `service_state`, a `counter` column on
      `known_documents`) that makes it fail and name the table.
- [ ] Settings: `KEYSERVICE_OPEN_RATE_PER_MINUTE` (120),
      `KEYSERVICE_OPEN_BURST` (30). Proved by: settings tests.
- [ ] The bucket: a burst past the caller's limit gets 429 with
      `Retry-After`; another caller is not affected; the order is 401, 422,
      429 (a request without a purpose over the limit gets 422). Proved by:
      tests.
- [ ] The 429 audit: 500 refused opens in one window → the counter is 500 and
      the chain grew by one `open_refused` record; one refusal in the next
      window → one `open_refused_summary` with 500, one new `open_refused`,
      counter 501. Proved by: a test that moves `now` across the window.
- [ ] Two app instances on one database (two replicas) refusing the same
      caller in one window write one `open_refused` record between them.
      Proved by: a test with two apps.
- [ ] `GET /v1/metrics`: 401 without a token; with one, opens per caller and
      purpose matching the `open` records, refusals per caller and reason
      matching `service_state`; no value, document id or object key in the
      output. Proved by: tests, and a diff showing `auth.py` untouched.
- [ ] `/v1/metrics` is never refused: called more often than
      `KEYSERVICE_OPEN_RATE_PER_MINUTE` allows with a valid token, no call is
      answered 429; the app has no path-keyed limiter middleware. Proved by:
      tests.
- [ ] ADR-0009: the open-rate residual extended with the metrics behind the
      service token and the coarser audit of 429s (no parallel row). Proved
      by: the ADR diff and a grep for `/v1/metrics` and
      `open_refused_summary` in it.
- [ ] Docs: the limit and its defaults, `Retry-After`, the coarser 429 audit,
      `/v1/metrics` (needs the service token), that the scraper's token is a
      homelab PR and that no alert is built, in
      `docs/reference/key-service-api.md` and `docs/how-to/key-service.md`;
      `service_state` where the key-service schema is described. Proved by:
      the docs check in CI and a grep for `service_state` and
      `open_refused_summary` in the docs.
