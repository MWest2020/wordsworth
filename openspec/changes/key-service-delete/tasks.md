# Tasks

Build B, fourth of four. Every test runs against FakeTransit and the service's
own test database, under the fixture that makes `config.settings` raise. No
traffic from wordsworth.

- [ ] `lifecycle.py`: `append_lifecycle` under 4783 and
      `verify_lifecycle_chain`, the same content and hash construction as
      wordsworth's `key_audit_pg`; the `AccessAudit` docstring says 4783.
      Proved by: tests that the chain verifies and that a record hashed by
      wordsworth's construction from the same fields gets the same hash.
- [ ] `DELETE /v1/originals/{id}` destroys the document's key rows, evicts the
      cache, answers `{"destroyed": n}`, is idempotent, and a later `open`
      answers 404. Proved by: tests.
- [ ] `DELETE /v1/documents/{id}` removes keys, registry rows, only the
      mappings no other document is registered for, and every grant scoped to
      the document (reporting a `grants` count), keeps unscoped grants, and
      leaves a tombstone; a later `pseudonymise` or `seal` of it answers 410.
      Proved by: tests, including a value shared by two documents and a
      document with a scoped and an unscoped grant.
- [ ] Already tombstoned and never seen: the counts as in `design.md`; a
      never-seen id gets no tombstone, its scoped grants are deleted and
      counted, and a later `pseudonymise` registers it. Proved by: tests.
- [ ] Both deletions write one lifecycle event and one `access_audit` record
      in one transaction; a failure injected after the lifecycle append
      commits neither. Proved by: tests, and both chains verifying after the
      run.
- [ ] Locks: two connections running a document deletion, an originals
      deletion and a seal against each other all complete, none aborted by a
      deadlock. Proved by: a test in the shape of `tests/race_setup.py` (hold
      one side, wait for a lock waiter).
- [ ] The #465 twin: a pseudonymise of a shared value for document B running
      against a deletion of document A leaves B's mapping in place, whichever
      commits first. Proved by: a test with two connections.
- [ ] No clear value, original byte or key byte in any response, log line or
      audit record of this change. Proved by: a response scan and a
      log-capture test with sentinels.
- [ ] Docs: both deletions with their status codes and counts in
      `docs/reference/key-service-api.md`, including the never-seen case.
      Proved by: the docs check in CI.
