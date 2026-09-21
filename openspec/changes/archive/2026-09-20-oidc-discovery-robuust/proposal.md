# Proposal: de sleutels van de uitgever ophalen zonder het internet, en zonder de app om te leggen

## Why

Bij het uitrollen van Keycloak liep wordsworth meteen vast:

```
wordsworth.access_identity.DiscoveryError: discovery unreachable for
issuer 'https://iam.westerweel.work/realms/westerweel': HTTPError
[1] [ERROR] Reason: Worker failed to boot.
```

Twee dingen zaten fout, en geen van beide is de instelling.

**1. De weg naar buiten en weer naar binnen.** De uitgever is publiek
bereikbaar, dus de pod ging via Cloudflare naar de eigen tunnel terug
het cluster in. Cloudflare weigert die aanvraag met **403**: de
`urllib`-aanroep stuurt geen User-Agent. Vanaf dezelfde pod geeft
`curl` netjes 200, en de interne Service ook. Een dienst die zijn buur
in hetzelfde cluster via het publieke internet bevraagt, hangt af van
twee extra partijen (de tunnel en de bot-regels van een CDN) voor iets
wat één netwerkhop verderop staat.

**2. Ophalen bij het opstarten is dodelijk.** De fetch gebeurt tijdens
het booten, en een fout daar sloopt de worker. Daarmee neemt een
hikkende identiteitsprovider de hele documentpijplijn mee — ook de
routes die niets met inloggen te maken hebben.

## What Changes

- Het JWKS-adres mag los ingesteld worden
  (`WORDSWORTH_OIDC_JWKS_URL`). Staat het er, dan wordt het discovery-
  document niet opgehaald en gaat het verkeer rechtstreeks naar de
  interne Service. De **uitgever blijft** de publieke naam, want dat is
  wat in `iss` staat en dus wat gecontroleerd moet worden.
- De fetch verhuist naar het moment dat hij nodig is, met cache: geen
  netwerkverkeer tijdens het opstarten, en een onbereikbare uitgever
  levert een geweigerd verzoek op in plaats van een dode app.
- De HTTP-aanroep stuurt een User-Agent, zodat de publieke route ook
  werkt voor wie hem tóch gebruikt.

## Scope / Not in scope

**In:** `access_identity.py` en de configuratie eromheen.

**Out:** de inlogstroom (die doet oauth2-proxy), rollen, grants, audit.
