# Tasks

Build B of three. Every test runs against FakeTransit and the service's own
test database. No traffic from wordsworth.

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
      past the caller's limit gets 429 and each refusal is audited; another
      caller's bucket is unaffected. Proved by: tests.
- [ ] `DELETE /v1/originals/{id}` destroys the keys and a later open is 404;
      `DELETE /v1/documents/{id}` removes keys, registry rows and only the
      mappings no other document is registered for, and leaves a tombstone.
      Proved by: tests, including a value shared by two documents.
- [ ] The #465 twin: a pseudonymise of a shared value for document B running
      against a deletion of document A leaves B's mapping in place, whichever
      commits first. Proved by: a test with two connections.
- [ ] `access_audit` is hash-chained and verifies after all of the above; no
      record holds a value, a key byte or original bytes. Proved by: tests.
- [ ] No clear value, original byte or key byte in any log line across every
      test in this change. Proved by: a log-capture test with sentinels.
- [ ] Docs: the five endpoints with their status codes in
      `docs/reference/key-service-api.md`; purposes, the rate limit and its
      defaults, and the pseudonymise residual in `docs/how-to/key-service.md`.
