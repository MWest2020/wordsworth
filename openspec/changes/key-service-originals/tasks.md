# Tasks

Build B, second of four. Every test runs against FakeTransit (and a fake that
raises a connect error or answers 4xx/5xx for the `OpenBaoTransit` cases) and
the service's own test database, under the fixture that makes
`config.settings` raise. No traffic from wordsworth.

- [ ] Settings: `KEYSERVICE_ORIGINALS_KEK` (defaults to
      `KEYSERVICE_TRANSIT_KEK`), `KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN`,
      `KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE` (1 024),
      `KEYSERVICE_MAX_ORIGINAL_BYTES` (100 MiB). Proved by: settings tests.
- [ ] `doc_keys.py` over the service's `DocumentKeyRecord`: mint, unwrap,
      evict, the bounded cache; `wordsworth.document_keys` is not imported.
      Proved by: tests,
      and a test that `wordsworth.document_keys` is absent from the service's
      import graph.
- [ ] `unwrap`'s classification: connect error, timeout and HTTP 5xx →
      `KeyBackendUnavailable`; HTTP 4xx and `InvalidTag` → `KeyDoesNotUnwrap`.
      Proved by: one test per case.
- [ ] Seal rule 1: a first seal mints, sets `sealed_at`, returns sealed bytes
      with `X-Key-Id`. Proved by: a test.
- [ ] Seal rule 2: a second seal of the same object key for the same document
      returns the same `X-Key-Id`, mints nothing, and the first sealed copy
      still opens. Proved by: a test.
- [ ] Seal rule 3: a seal of an object key whose row belongs to another
      document → 409 and nothing written. Proved by: a test.
- [ ] Seal refusals: 413 over the bound, 422, 409 other domain, 410
      tombstoned, 503 with nothing committed. Proved by: tests.
- [ ] `known_documents` through `known.py`: a document first sealed in domain
      A and then pseudonymised or sealed in domain B → 409. Proved by: tests.
- [ ] Open: the seal/open round trip returns the original bytes; a purpose
      missing or outside the list → 422 and nothing decrypted; no row for the
      object key under this document → 404 with an `open_refused` record.
      Proved by: tests.
- [ ] Open fails closed: a tampered wrapped key → 409 `open_failed`
      `reason = "unwrap"`; a tampered envelope → 409 `open_failed`
      `reason = "envelope"`; neither returns plaintext. Transit unreachable →
      503 and no audit record. Proved by: tests.
- [ ] Every successful open writes one `access_audit` record with its
      purpose; every seal one with minted or reused. Proved by: tests.
- [ ] No original byte or key byte in any log line or audit record. Proved
      by: a log-capture test with a sentinel original.
- [ ] Modules and the 200-line invariant: seal stays in `api_originals.py`,
      open lives in `api_open.py`, as design.md "Modules" says; `doc_keys.py`
      and both route files are ≤ 200 lines. Proved by: a check that
      `wc -l` of each of `doc_keys.py`, `api_originals.py`, `api_open.py` and
      `config.py` is ≤ 200 (the reviewer's FAIL on wordsworth#544 was
      `api_originals.py` at 202), and a grep that the open route is defined
      in `api_open.py` and not in `api_originals.py`.
- [ ] The real artefact, required PR evidence (not optional; the PR is not
      done without it): against the OpenBao of `key-service-pseudonymise`'s
      smoke run, seal one original and open it again with a purpose, and the
      bytes come back identical. Proved by: the commands and their output
      pasted in the PR description.
- [ ] ADR-0009: one risk line, the wire (`open` returns and `seal` receives
      plaintext over HTTP; the deployment's TLS is the mitigation). Proved by:
      the ADR diff and a grep for `plaintext over HTTP` in it.
- [ ] Docs: seal and open with their status codes, the purposes and the size
      bound in `docs/reference/key-service-api.md`; the settings and the wire
      in `docs/how-to/key-service.md`. Proved by: the docs check in CI.
