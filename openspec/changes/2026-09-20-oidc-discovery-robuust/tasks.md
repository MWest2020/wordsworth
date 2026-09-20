# Tasks: oidc-discovery-robuust

## 1. Ophalen — run 01
- [ ] 1.1 `WORDSWORTH_OIDC_JWKS_URL`: staat die gezet, dan wordt het
  discovery-document overgeslagen en gebruikt de verificatie dat adres.
  De uitgever blijft gecontroleerd tegen `iss`.
- [ ] 1.2 Geen netwerkverkeer tijdens het opstarten: ophalen gebeurt bij
  het eerste verzoek dat een token controleert, met cache. Een
  onbereikbare uitgever geeft "geen caller" (fail-closed), geen crash.
- [ ] 1.3 De HTTP-aanroep stuurt een User-Agent mee.
- [ ] 1.4 Tests: met JWKS-adres wordt discovery niet opgehaald; zonder
  adres wel (en gecached); een fout bij het ophalen geeft geen caller en
  laat de app draaien; de User-Agent staat op het verzoek.

## 2. Documentatie
- [ ] 2.1 Deployment-documentatie + CHANGELOG onder `[Unreleased]`.
