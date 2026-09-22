# Habitat run 01 — OIDC-identiteit (tasks 1.1–2.1)

Contract: `openspec/changes/2026-09-20-keycloak-identity/`.

## Scope — ONLY these tasks
- [ ] 1.1 `src/wordsworth/access_identity.py`: `Verifier` krijgt
  uitgever, publiek en JWKS-adres als velden. De Cloudflare-variant
  (team_domain → certs_url/issuer) blijft werken; bouw hem als één
  manier om een Verifier te maken, niet als apart pad door de code.
- [ ] 1.2 Token lezen uit `Authorization: Bearer …` én uit
  `cf-access-jwt-assertion`. `cf-access-authenticated-user-email` blijft
  onvertrouwd — de constante die dat vastlegt blijft staan.
- [ ] 1.3 `config.py`: `WORDSWORTH_OIDC_ISSUER` en
  `WORDSWORTH_OIDC_AUDIENCE`; JWKS-adres uit
  `<issuer>/.well-known/openid-configuration` (`jwks_uri`), met cache en
  een nette fout als het discovery-document onbereikbaar is.
- [ ] 1.4 Tests met zelfondertekende sleutels (geen netwerk): geldig
  token → caller; verkeerde uitgever / verkeerd publiek / verlopen /
  kapotte handtekening → geen caller; geen token en geen sleutel →
  fail-closed.
- [ ] 2.1 Deployment-documentatie + CHANGELOG onder `[Unreleased]`.

Raak rollen, grants, audit en de console niet aan.

## Done means
`uv run pytest -q` groen en `openspec validate 2026-09-20-keycloak-identity
--strict` groen. Budget is $5.
