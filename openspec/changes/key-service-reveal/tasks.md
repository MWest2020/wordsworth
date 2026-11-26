# Tasks

Build C of three. Tests run against FakeTransit, the service's own test
database, and assertions signed by a test key the service is configured to
trust (the pattern of wordsworth's existing identity tests). Grants and roles
are seeded as rows; no management endpoint is built here. No traffic from
wordsworth.

- [ ] Identity: `KEYSERVICE_OIDC_*` settings; a forged signature, an expired
      or not-yet-valid token, a wrong issuer and a foreign audience each get
      401 `assertion not accepted` with the same body, and no statement reads
      `grants`, `known_documents`, `document_tokens` or `pii_mappings`.
      Without issuer and audience configured both routes answer 503. Proved
      by: tests.
- [ ] `wordsworth-keyservice-init` ensures the admin role. Proved by: a test.
- [ ] `/v1/reveal/decide` follows the order of `design.md`: for an unknown
      grant, a revoked, expired, other-recipient or other-document grant, no
      statement reads `known_documents`, `document_tokens`, `pii_mappings` or
      `key_vault`; it writes no record. Proved by: tests counting statements
      per table.
- [ ] One refusal: an unknown grant, a revoked grant, an expired grant, a
      grant for another document, another recipient, another domain, an
      unknown document and a tombstoned document outside the grant's scope all
      give 403 with the identical body `{"detail": "grant not applicable"}`,
      on both routes. Proved by: a test comparing status, body and content
      type.
- [ ] Covered callers: a tombstoned document gives 410; a rejected VC gives
      403 `vc rejected: …` and never 410. Proved by: tests.
- [ ] `/v1/reveal` reveals only requested tokens that are registered for the
      document and of an authorised type: a token registered only for document
      B, sent in a reveal of document A by a caller covered for A with that
      type, is not revealed and not named. Proved by: a test (this is
      ADR-0009's threat-model row).
- [ ] A registered token of an authorised type that was not requested is not
      revealed; a missing key version leaves the token unresolved; Transit down
      gives 503 and no record. Proved by: tests.
- [ ] The PDF view returns `resolved_tokens` and no `values`. Proved by: a
      test asserting the whole body.
- [ ] Each successful reveal appends one `access_audit` record with the fields
      of `design.md` and no value; `resolved_types` in the response equals the
      record's `types`; the chain verifies. Proved by: tests.
- [ ] A refusal writes no record, and no captured log line contains the words
      "unknown", "superseded" or "deleted", a survivor id or the cause.
      Proved by: a log-capture test across every refusal cause.
- [ ] Decided afresh: a grant revoked, or a role switched off, between
      `decide` and `reveal` makes `reveal` answer 403. A group-held role never
      authorises a reveal (#495). Proved by: tests.
- [ ] The real artefact: start the service on a scratch database, seed a
      grant, a document and a pseudonymised value, and `curl` decide and
      reveal with a test-signed assertion: once covered, once with another
      document's token, once without an assertion. Proved by: the commands and
      output in the PR description.
- [ ] Docs: both endpoints with every status code in
      `docs/reference/key-service-api.md`; the identity settings, the audience
      choice and its cost, and the replay residual in
      `docs/how-to/key-service.md`.
