# Tasks

- [ ] The service starts with its own database and refuses to start with
      wordsworth's database URL. Proved by: a test.
- [ ] API contract tests for each endpoint against FakeTransit: pseudonymise
      returns tokens only (no value in the response), reveal returns only the
      authorised types, seal/open round-trip, delete makes open fail. Proved
      by: tests.
- [ ] Security tests: a call without the service token is refused; a reveal
      with a forged/expired/foreign-audience assertion is refused; a tampered
      wrapped key fails closed; no clear value or key byte appears in logs
      during any of these. Proved by: tests.
- [ ] Every `open` writes an audit record with its purpose; the rate limit
      refuses a burst. Proved by: tests.
- [ ] Docs: `docs/reference/key-service-api.md` (the contract) and
      `docs/how-to/key-service.md` (deploying, its database, failure modes).
