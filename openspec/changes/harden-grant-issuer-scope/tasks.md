## 1. Scope

- [x] 1.1 `config.grant_issuer_labels` uit `WORDSWORTH_GRANT_ISSUER_LABELS`.
- [x] 1.2 `auth.authorize_grant_issue` — puur, fail-closed met auth aan.
- [x] 1.3 `_guard_grant_admin` vóór de write in issue én revoke.
- [x] 1.4 `auth_enabled` uit de effectieve keys (inclusief config-fallback).

## 2. Gate

- [x] 2.1 Test: zonder auth ongewijzigd (201).
- [x] 2.2 Test: met auth mint alleen een issuer-label; ander label 403.
- [x] 2.3 Test: lege kring + auth aan weigert iedereen.
- [x] 2.4 Test: intrekken valt onder dezelfde scope.
- [x] 2.5 Volledige suite groen (445 passed, 11 skipped).
- [x] 2.6 `openspec validate --strict` + CI groen.

## 3. Deploy

- [x] 3.1 `WORDSWORTH_GRANT_ISSUER_LABELS: "console,cli"` staat in
      `cluster-config/infra/wordsworth/configmap.yaml` (homelab 5d5b4be,
      gepusht). ArgoCD synct die app automatisch.
- [ ] 3.2 Live bevestigen dat de pod de waarde heeft
      (`kubectl -n wordsworth get cm wordsworth-config -o jsonpath=...`) en dat
      een issuer-label wél en een ander label géén grant mint. Kon nu niet:
      jumpy is onbereikbaar (ssh time-out).
