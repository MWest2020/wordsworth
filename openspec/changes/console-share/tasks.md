# Tasks

## 1. Sharing
- [ ] `grants.share(session, scope, recipient, ppl|role, expires, actor)` issues
      one grant per live document in scope (document, topic, dossier) under one
      share id. Proved by: a unit test for each scope.
- [ ] Only `beheerder` or an issuer label may share. Proved by: a test that any
      other caller is refused and nothing is issued.
- [ ] Revoking a share revokes all its grants. Proved by: a test.
## 2. Console
- [ ] "Delen" on the document, topic and dossier pages; a result page listing
      the redacted PDF links. Proved by: console tests.
## 3. Docs
- [ ] `docs/how-to/grants.md`: sharing from the console, defaults, revoking.
