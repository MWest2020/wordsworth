# Tasks

Build B of three. Every test runs against FakeTransit and the service's own
test database. No traffic from wordsworth.

- [ ] First, settle `docs/reference/lock-order.md`: add the key-lifecycle chain
      to the order, `key_lifecycle_events` before `access_audit` (the audit
      stays the terminal leaf), and note that `DELETE /v1/originals` and
      `DELETE /v1/documents` take both in that order in one transaction.
      Proved by: the page diff, and a test with two connections that runs the
      two deletes against each other and a plain `open` and finds no deadlock.
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
- [ ] Seal/open round trip; `open` without a purpose or with one outside the
      list → 422; a tampered wrapped key or envelope → 409 and
      `open_failed`, never plaintext; Transit down → 503. Proved by: tests.
- [ ] Every `open` writes an `access_audit` record with its purpose; a burst
      past the caller's limit gets 429, every refusal increments
      `keyservice_open_refusals_total{reason="rate"}`, and the audit gets one
      `open_refused` record per caller per 60-second window plus one
      `open_refused_summary` with the final count, not one record per refusal;
      another caller's bucket is unaffected. Proved by: a test firing 500
      refused opens and asserting the counter is 500 and the chain grew by two
      records.
- [ ] `pseudonymise` refuses more than `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS`
      (default 1 000) with 422, and the service refuses to start with the
      setting above 5 000. Proved by: tests at the cap, cap + 1 and a start
      with 5 001.
- [ ] Measurement at cutover (carried into `key-service-cutover`'s tasks): the
      time lock 4781 is held by a batch of the cap size against the real
      database, and the other writers' wait during it, recorded in the cutover
      evidence; the default is changed from it if the wait is not acceptable.
      Proved by: the figures in the cutover change's evidence.
- [ ] `DELETE /v1/originals/{id}` destroys the keys and a later open is 404;
      `DELETE /v1/documents/{id}` removes keys, registry rows, only the
      mappings no other document is registered for, and every grant scoped to
      the document (reporting a `grants` count), keeps unscoped grants, and
      leaves a tombstone. Proved by: tests, including a value shared by two
      documents and a document with a scoped and an unscoped grant.
- [ ] No route of this change returns a clear mapping value: every response
      body across the tests is scanned for the sentinel values. Proved by: a
      test.
- [ ] Metrics are mounted at `GET /v1/metrics`, covered by the existing
      `ServiceTokenMiddleware` (unchanged; 401 without a token) and count opens
      and open refusals per caller and purpose or reason, with no value or
      document id. Proved by: a test with and without a token.
- [ ] `/v1/metrics` stays exempt from rate limiting: `rate_limit.EXEMPT_PATHS`
      gains it, and the homelab scraper config points at `/v1/metrics` with its
      own service token. Proved by: `tests/test_rate_limit.py` (the updated
      `EXEMPT_PATHS` assertion) and a test of more calls than the limit with
      none answered 429; the scraper config diff in the homelab manifest.
- [ ] The 429 summary is written lazily (next window's first refusal, or
      graceful shutdown). Proved by: a test with a clock that moves past the
      window and one that stops the service with a window open.
- [ ] The #465 twin: a pseudonymise of a shared value for document B running
      against a deletion of document A leaves B's mapping in place, whichever
      commits first. Proved by: a test with two connections.
- [ ] `access_audit` is hash-chained and verifies after all of the above; no
      record holds a value, a key byte or original bytes. Proved by: tests.
- [ ] No clear value, original byte or key byte in any log line across every
      test in this change. Proved by: a log-capture test with sentinels.
- [ ] Write the three residuals into ADR-0009's threat model
      (`docs/explanation/adr/0009-separate-key-and-reveal-service.md`),
      extending the rows already there (open rate and no alert, crypto-shred by
      the credential alone, `pseudonymise` as guess-confirmation) with the
      metrics behind the service token, the coarser audit of 429s and the batch
      cap, not adding parallel rows. Proved by: the ADR diff and a grep for
      `/v1/metrics` and `open_refused_summary` in it.
- [ ] Docs: the five endpoints and `/v1/metrics` (needs the service token) with
      their status codes and the batch cap in
      `docs/reference/key-service-api.md`; purposes, the rate limit and its
      defaults, the coarser audit of 429s, that no alert is built yet, and the
      three residuals in `docs/how-to/key-service.md`; the rate-limit exemption
      for `/v1/metrics` where `docs/how-to/api-auth.md` and the rate-limit
      docs list exempt paths. Proved by: the docs check in CI and a grep for
      the cap and `open_refused_summary` in both.
