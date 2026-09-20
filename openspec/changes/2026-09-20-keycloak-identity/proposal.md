# Proposal: identiteit uit Keycloak, niet uit Cloudflare Access

## Why

Wordsworth vertrouwt vandaag op Cloudflare Access voor "wie is dit": de
edge zet een ondertekende JWT in `cf-access-jwt-assertion`, en
`access_identity.py` controleert die tegen de JWKS van het team. Dat
werkt, maar het legt de identiteit van de mensen die met
pseudonimisering van persoonsgegevens werken bij een Amerikaanse
dienst — precies de afhankelijkheid die dit huis bij anderen aanwijst.

Sinds 2026-09-20 draait er een eigen identiteitsprovider in het
homelab: Keycloak op `iam.westerweel.work`, realm `westerweel`
(homelab-repo, `cluster-config/infra/keycloak/`). Wanderer logt er al
op in. Wordsworth is de volgende.

De code is er bijna klaar voor. `roles.py` zegt het zelf:

> Wat hier NIET woont: wie iemand is. Dat komt uit de aanmelding
> (Cloudflare Access, en ooit iets als Keycloak).

En `access_identity.Verifier` is al een gewone JWT-controle: wiens
sleutels, voor welke toepassing. Wat ontbreekt is dat die sleutels en
die uitgever uit configuratie komen in plaats van uit een
Cloudflare-teamnaam.

## What Changes

- `access_identity` wordt een OIDC-verificatie: uitgever, publiek (aud)
  en JWKS-adres komen uit configuratie. Cloudflare Access blijft één
  mogelijke invulling daarvan; Keycloak is de tweede.
- Het token mag ook uit `Authorization: Bearer …` komen, want dat is
  wat een omgekeerde proxy (oauth2-proxy) voor Keycloak meestuurt. De
  `cf-access-jwt-assertion`-kop blijft werken zolang die er is.
- De caller blijft het geverifieerde e-mailadres uit het token. Rollen,
  grants en het auditspoor veranderen niet: die kennen alleen namen.
- API-sleutels blijven bestaan voor machines. Een verzoek met een
  geldig token én een sleutel gebruikt het token.

## Scope / Not in scope

**In:** `access_identity.py`, de configuratie eromheen, en het
aanhaken in `api.py`.

**Out:** rollen, grants, audit, de console-frontend, en het uitrollen
zelf (oauth2-proxy + Keycloak-client staan in de homelab-repo). Ook
niet: netnl — dat is een machine-API met een anonieme demo, daar hoort
geen inlogscherm voor.

## Risico dat expliciet benoemd hoort

Een JWT-controle die per ongeluk terugvalt op "geen token = geen
caller" maakt van een gesloten deur een open deur zodra de proxy
wegvalt. Fail-closed blijft: geen geldig token en geen geldige sleutel
betekent geen caller, en een caller-loze aanvraag mag geen grant
uitgeven of volledige tekst lezen.
