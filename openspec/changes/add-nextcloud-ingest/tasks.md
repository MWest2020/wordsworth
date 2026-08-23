## 1. WebDAV source

- [x] 1.1 `NextcloudClient` (PROPFIND list + recurse, GET fetch) behind a
  `WebDavSource` protocol; `parse_propfind` strips the dav-files prefix + excludes
  the queried collection.
- [x] 1.2 `ingest_from_nextcloud(client, ingest_one, folder)` — PDF-only,
  idempotent (via ingest_one), continue-on-failure, returns per-outcome counts.

## 2. Surfaces (additive, default-off)

- [x] 2.1 Config `WORDSWORTH_NEXTCLOUD_{URL,USER,PASSWORD,FOLDER}`; `configured()`
  inert when empty; password never logged.
- [x] 2.2 `POST /ingest/nextcloud` mounts only when configured, reuses `_ingest_one`.
- [x] 2.3 CLI `wordsworth ingest-nextcloud [--folder]`; reports not-configured.

## 3. Gate

- [x] 3.1 Local tests: XML parse, recursion, driver idempotency+continue-on-fail,
  inert, CLI; local suite green (259 passed).
- [ ] 3.2 DB-integration (CI): end-to-end pull through the real pipeline.
- [ ] 3.3 Full suite green in CI + `openspec validate`.
