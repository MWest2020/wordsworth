## 1. Endpoint

- [x] 1.1 `RevealRequest{grant_id, types?}` / `RevealResponse{document_id,
  revealed_text, revealed_types, withheld_types, grant_id}`.
- [x] 1.2 `POST /documents/{document_id}/reveal`: grant lookup, applicability
  (403), doc + de-identified checks (404/409), `authorize` → `deanonymize`.
- [x] 1.3 `create_app` gains `key_provider`/`grant_store`; route mounted only when
  both + `session_factory` present (default deployment unchanged).

## 2. Gate

- [x] 2.1 Local: route mounts iff deps present; suite green (204 passed).
- [ ] 2.2 DB-integration (CI): granted type revealed + others withheld; defaults
  to grant types; revoked→403; unknown grant/doc→404; other-document grant→403;
  reveal audited (recipient actor, types, no clear values, chain verifies).
- [ ] 2.3 CI green + `openspec validate`.
