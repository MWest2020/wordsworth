## 1. Endpoint

- [x] 1.1 `create_app` gains `store` + `anonymizer`; register `POST /ingest` when
  session_factory + store + search_index + embedder are wired.
- [x] 1.2 Route drives ingest → OCR recovery → anonymize → store → index; returns
  `{document_id, filename, state}`; anonymizer defaults to OpenAnonymiser.
- [x] 1.3 Fail-hard: 400 on empty upload, 502 carrying only the error class name
  (no document text); per-doc transaction rolls back on failure.

## 2. Wiring + deps

- [x] 2.1 `serve.build_app` wires store + anonymizer only when S3 creds present.
- [x] 2.2 Add `python-multipart`.

## 3. Tests + gate

- [x] 3.1 Offline: `/ingest` registered with store+deps, absent without.
- [x] 3.2 Full suite green (153 passed) + `openspec validate --all`.
