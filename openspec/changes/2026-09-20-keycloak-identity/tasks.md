# Tasks: keycloak-identity

## 1. Verificatie — run 01
- [ ] 1.1 `access_identity.Verifier` krijgt uitgever, publiek en
  JWKS-adres uit configuratie (OIDC), met Cloudflare Access als één
  invulling ervan. Bestaande Access-configuratie blijft geldig.
- [ ] 1.2 Het token wordt gelezen uit `Authorization: Bearer …` én uit
  `cf-access-jwt-assertion`; het e-mailadres uit de kop blijft
  onvertrouwd.
- [ ] 1.3 Configuratie: uitgever + publiek voor Keycloak
  (`WORDSWORTH_OIDC_ISSUER`, `WORDSWORTH_OIDC_AUDIENCE`), JWKS via het
  discovery-document van de uitgever, met cache.
- [ ] 1.4 Tests: geldig Keycloak-token geeft de caller; verkeerde
  uitgever, verkeerd publiek, verlopen token en verkeerde handtekening
  geven allemaal geen caller; zonder token en zonder sleutel blijft het
  fail-closed.

## 2. Documentatie
- [ ] 2.1 Deployment-documentatie + CHANGELOG onder `[Unreleased]`.
