# Tasks

Build A of three (see `proposal.md`). No traffic: nothing in wordsworth calls
the service after this change.

- [ ] Package `src/wordsworth/keyservice/` with `config.py`, `models.py`,
      `db.py`, `bootstrap.py`, `auth.py`, `serve.py`, every file ≤ 200 lines;
      scripts `wordsworth-keyservice` and `wordsworth-keyservice-init` in
      `pyproject.toml`. Proved by: `uv run ruff check src/ tests/` and the
      tests below.
- [ ] Its own settings: `KEYSERVICE_DATABASE_URL` (required) and
      `KEYSERVICE_SERVICE_TOKENS`; reused functions that read wordsworth's
      `config.settings` (`document_keys.kek_name_for`, `DocumentKeys` cache
      defaults) take their values as arguments in the service, wordsworth's
      call sites unchanged. Proved by: a test that sets conflicting
      `WORDSWORTH_*` values and shows the service uses `KEYSERVICE_*`.
- [ ] `KeyServiceBase` with the tables of `design.md` ("Schema"), including
      the token registry `document_tokens` and `known_documents`; no foreign
      key to a wordsworth table; neither metadata imports the other. Proved
      by: a test that init on an empty database creates exactly the service's
      tables and none of wordsworth's; a second init is a no-op.
- [ ] Append-only `access_audit` and `key_lifecycle_events`: UPDATE and DELETE
      raise. Proved by: a test.
- [ ] Drift check: for every copied table, the service's column names and
      types equal wordsworth's model. Proved by: a test that fails naming the
      column (shown failing once by a deliberately altered copy in the test).
- [ ] Refuse to start (the three rules of `design.md`): no URL; the same
      database as `WORDSWORTH_DATABASE_URL`; a database holding
      `audit_records` or `document_texts`. Proved by: a test per rule, for both
      the server and the init entrypoint.
- [ ] Service token, fail-closed: `/v1/*` without a token, with an unknown
      token, or with an empty token set answers 401 before any database read;
      `/health` answers without a token. Proved by: tests (the "before any
      read" part by counting statements).
- [ ] Test fixture: a private service test database; dropping and creating
      `KeyServiceBase.metadata` leaves wordsworth's test tables untouched.
      Proved by: a test.
- [ ] The real artefact, from the side that holds no key: run
      `wordsworth-keyservice-init` against a scratch database, start
      `wordsworth-keyservice`, `curl /health` (200) and `curl` a `/v1` path
      without a token (401). Proved by: the commands and their output in the
      PR description.
- [ ] Docs: `docs/how-to/key-service.md` (deploying, its database and role,
      the refuse-to-start rules, the service token, failure modes, and that
      until the homelab NetworkPolicy exists anything holding a service token
      reaches the service). `docs/reference/key-service-api.md` starts with
      `/health` and the 401; the later changes add their endpoints.
