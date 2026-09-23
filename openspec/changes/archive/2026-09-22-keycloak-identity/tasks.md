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

## 4. Correctie (2026-09-23): dit draait al sinds 2026-09-20

Bij het archiveren schreef ik hier dat deze change "gebouwd maar slapend" was:
uitgever en publiek zouden niet gezet zijn, dus de identiteit liep nog via
Cloudflare Access. **Dat was fout.**

Uitgever en publiek staan in de `env:` van de Deployment zelf
(`homelab: cluster-config/infra/wordsworth/api.yaml`, sinds `43ff7fb` op
2026-09-20), niet in de configmap. Ik controleerde alleen de configmap, zag daar
alleen het JWKS-adres, en trok de conclusie zonder de tweede plek te bekijken
waar een waarde vandaan kan komen. Gecontroleerd in de draaiende pod: de
verifier die in gebruik is, heeft als uitgever de Keycloak-realm. Met beide
ingesteld wint OIDC van Cloudflare Access.

Het archief laat de oorspronkelijke tekst niet stil verdwijnen: dit is een
feitelijke fout die ik er zelf in schreef, geen stand van toen die sindsdien
veranderde.

Wat van de toenmalige waarschuwing overeind blijft: een grant op een
sleutellabel is inert voor wie via Keycloak binnenkomt. Die was er nog één
(`console`, `df24139e`, één document, eenmaal gebruikt op 2026-09-17); op
2026-09-23 ingetrokken via `POST /grants/{id}/revoke`, en
`wordsworth-access-preflight` meldt daarna: geen actieve grants op een
sleutellabel.
