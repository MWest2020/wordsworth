# Tasks: keycloak-identity

## 1. Verificatie — run 01
- [x] 1.1 `access_identity.Verifier` krijgt uitgever, publiek en
  JWKS-adres uit configuratie (OIDC), met Cloudflare Access als één
  invulling ervan. Bestaande Access-configuratie blijft geldig.
- [x] 1.2 Het token wordt gelezen uit `Authorization: Bearer …` én uit
  `cf-access-jwt-assertion`; het e-mailadres uit de kop blijft
  onvertrouwd.
- [x] 1.3 Configuratie: uitgever + publiek voor Keycloak
  (`WORDSWORTH_OIDC_ISSUER`, `WORDSWORTH_OIDC_AUDIENCE`), JWKS via het
  discovery-document van de uitgever, met cache.
- [x] 1.4 Tests: geldig Keycloak-token geeft de caller; verkeerde
  uitgever, verkeerd publiek, verlopen token en verkeerde handtekening
  geven allemaal geen caller; zonder token en zonder sleutel blijft het
  fail-closed.

## 2. Documentatie
- [x] 2.1 Deployment-documentatie + CHANGELOG onder `[Unreleased]`.

## 3. Archiveren (2026-09-22)
- [x] De eis is gesynct naar `specs/api-key-auth`, in het Engels, samen met de
      Nederlandse buureis uit `oidc-discovery-robuust` — een spec half in twee
      talen leest slechter dan een spec in de verkeerde taal.
- [x] Bij het synchroniseren toegevoegd wat de code al doet maar de delta niet
      zei: uitgever én publiek zijn allebei nodig vóórdat er überhaupt een
      OIDC-verifier bestaat (`config.py`). Een JWKS-adres alleen is het ADRES van
      de sleutels, niet het besluit ze te gebruiken.

## 4. Niet gedaan, en met opzet: aanzetten
- [ ] **Voor Mark.** In de configmap staat alleen `WORDSWORTH_OIDC_JWKS_URL`;
      `WORDSWORTH_OIDC_ISSUER` en `WORDSWORTH_OIDC_AUDIENCE` niet. De
      identiteit draait dus nog op Cloudflare Access en deze change is gebouwd
      maar slapend.
      Aanzetten is geen config-tweak: op het moment dat callers identiteiten
      worden, autoriseert elke grant die aan een sleutel-label (`console`,
      `cli`) is uitgegeven niemand meer. `wordsworth-access-preflight` rapporteert
      welke dat zijn en verandert niets. Die grants worden niet gevaarlijk, ze
      worden inert — en een inerte grant die als "actief" in de tabel staat is
      een leugen.
