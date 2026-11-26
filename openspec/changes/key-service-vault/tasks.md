# Tasks

Build B of three, after the split (`open` is `key-service-open`). Every test
runs against FakeTransit and the service's own test database. No traffic from
wordsworth.

- [ ] First, settle `docs/reference/lock-order.md`: add the service's order
      (registry 4781, rows, key lifecycle 4783, audit 4782 last), say that
      `DELETE /v1/originals` and `DELETE /v1/documents` take 4783 then 4782 in
      one transaction, and that wordsworth's "never together with 4771" is
      about wordsworth's database. Proved by: the page diff, and a test with
      two connections that runs the two deletes against each other and a
      `seal` and finds no deadlock.
- [ ] `service_state` as in `design.md` (`kind`, `key`, `counter`, `data`,
      `updated_at`; PK `kind`, `key`), written only by `state.py`;
      `rate_limit_buckets` is no longer a copied table of the service and
      `RateLimitBucket` leaves `_COPIED_PAIRS` in `test_drift.py`. Proved by:
      `tests/keyservice/test_drift.py` still green without that pair, and the
      init test listing exactly the service's tables including `service_state`.
- [ ] `tests/keyservice/test_service_state_drift.py` next to `test_drift.py`:
      the columns of `service_state`, every table classified (copied, own, or
      `service_state`), no counter or window column elsewhere, absent from
      wordsworth's metadata, and `state.py` never reads `access_audit`.
      Proved by: that test, and a mutation (an extra column, a counter column
      on `known_documents`) that makes it fail and name the table.
- [ ] `document_keys.kek_name_for` takes the domain → KEK mapping as an
      argument and the service passes `KEYSERVICE_*` values to it and to
      `DocumentKeys`; wordsworth's call sites behave as before; this change's
      tests run under the skeleton's fixture that makes `config.settings`
      raise. Proved by: the existing wordsworth tests and the new ones.
- [ ] `POST /v1/pseudonymise` as in `design.md`: tokens equal to what
      wordsworth's `Pseudonymizer` yields for the same value, type and domain;
      the response body (asserted whole, not per field) holds no value; an
      empty batch registers the document. Proved by: tests.
- [ ] Registry: each returned token is registered for that document with
      `source = minted`; re-pseudonymising adds and never removes; nothing
      else writes `document_tokens`. Proved by: tests.
- [ ] `known_documents`: first call records the domain; another domain → 409;
      a tombstoned document → 410, for both `pseudonymise` and `seal`. Proved
      by: tests.
- [ ] `POST /v1/originals/{id}/seal` returns sealed bytes with `X-Key-Id`; a
      body over `KEYSERVICE_MAX_ORIGINAL_BYTES` → 413; Transit down → 503 with
      nothing committed. Proved by: tests (the round trip back to plaintext
      is proved in `key-service-open`).
- [ ] `pseudonymise` refuses more than `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS`
      (default 1 000) with 422, and the service refuses to start with the
      setting above 5 000. Proved by: tests at the cap, cap + 1 and a start
      with 5 001.
- [ ] Measurement at cutover (carried into `key-service-cutover`'s tasks): the
      time lock 4781 is held by a batch of the cap size against the real
      database, and the other writers' wait during it, recorded in the cutover
      evidence; the default is changed from it if the wait is not acceptable.
      Proved by: the figures in the cutover change's evidence.
- [ ] `DELETE /v1/originals/{id}` destroys the keys and evicts the cache;
      `DELETE /v1/documents/{id}` removes keys, registry rows, only the
      mappings no other document is registered for, and every grant scoped to
      the document (reporting a `grants` count), keeps unscoped grants, and
      leaves a tombstone. Proved by: tests, including a value shared by two
      documents and a document with a scoped and an unscoped grant.
- [ ] The #465 twin: a pseudonymise of a shared value for document B running
      against a deletion of document A leaves B's mapping in place, whichever
      commits first. Proved by: a test with two connections.
- [ ] No route of this change returns a clear mapping value: every response
      body across the tests is scanned for the sentinel values. Proved by: a
      test.
- [ ] `GET /v1/metrics` is mounted under `/v1/`, covered by the existing
      `ServiceTokenMiddleware` (unchanged; 401 without a token), renders the
      `counter` rows of `service_state` and no value or document id. Proved by:
      a test with and without a token, with a counter the test writes itself,
      and a diff showing the middleware file untouched.
- [ ] `access_audit` is hash-chained and verifies after all of the above; no
      record holds a value, a key byte or original bytes. Proved by: tests.
- [ ] No clear value, original byte or key byte in any log line across every
      test in this change. Proved by: a log-capture test with sentinels.
- [ ] Write the residuals into ADR-0009's threat model
      (`docs/explanation/adr/0009-separate-key-and-reveal-service.md`),
      extending the rows already there (open rate and no alert, crypto-shred by
      the credential alone, `pseudonymise` as guess-confirmation) with the
      metrics behind the service token, the coarser audit of 429s and the batch
      cap, and add one risk line: `open` returns plaintext over HTTP on the
      wordsworth-to-service link, so the wire is in the residuals. Proved by:
      the ADR diff and a grep for `/v1/metrics`, `open_refused_summary` and
      `plaintext over HTTP` in it.
- [ ] Docs: the endpoints of this change and `/v1/metrics` (needs the service
      token) with their status codes and the batch cap in
      `docs/reference/key-service-api.md`; `service_state` and the lock order
      where `docs/reference/lock-order.md` and the key-service schema docs
      describe the service's tables; the residuals, including the wire, in
      `docs/how-to/key-service.md`. Proved by: the docs check in CI and a grep
      for the cap, `service_state` and `plaintext over HTTP` in the docs.
