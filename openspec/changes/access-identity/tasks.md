# Tasks

Nog niet gebouwd. Vraag 2 is beantwoord langs de rollen-beslissing: de
(super)admin geeft de bestaande grants opnieuw uit op een identiteit. Wat deze
change moet doen is ze **benoemen vóór de omschakeling**, want bij de
recipient-binding merkten we pas achteraf dat er vier stil waren gevallen.

## 1. De verificatie
- [ ] RS256-verificatie tegen `/cdn-cgi/access/certs` van het team, met `aud`
      en `exp`. Liever met `cryptography` (staat er al) dan met een nieuwe
      afhankelijkheid: een handtekening controleren is minder code dan een
      bibliotheek erbij.
- [ ] De sleutels cachen met een korte houdbaarheid; Cloudflare rouleert ze.
      Een mislukte verversing is geen reden om een oude sleutel eeuwig te
      vertrouwen, en ook geen reden om iedereen buiten te zetten — dat verschil
      moet in de code staan en niet in de hoop.
- [ ] Geen configuratie = geen identiteit. Fail-closed, en niet
      waarschuwen-en-doorgaan.

## 2. Het label
- [ ] Een geldige identiteit wordt de caller in `scope["state"]`, waar het
      api-sleutel-label nu komt. Eén beslispunt, nu drie transportvormen:
      header, cookie, en een geverifieerde assertie.
- [ ] De console slaat het sleutelformulier over als er al een identiteit is.

## 3. Wat er NIET verandert
- [ ] De tailnet-route en API-clients houden hun sleutel. Een installatie zonder
      Cloudflare ervoor werkt ongewijzigd — anders is dit niet meer soeverein te
      draaien, en dat is het hele punt.

## 4. Bewijs
- [ ] Een test die een verzoek mét `Cf-Access-Authenticated-User-Email` en
      zónder geldige JWT géén identiteit geeft. Dat is de kern.
- [ ] Een test met een geldig ondertekende JWT voor een ándere `aud`.
- [ ] Een test dat het auditrecord de persoon noemt en niet het sleutellabel.
- [ ] Live: inloggen via Access en kijken of het auditspoor een e-mailadres
      toont in plaats van `console`.

## De correctie op het issue
In #81 schreef ik dat de tailnet-route dit onbruikbaar maakt omdat daar iedereen
de header kan zetten. Dat geldt voor de header en niet voor de JWT: een
handtekening is niet te vervalsen. Wie de JWT verifieert in plaats van de header
te geloven is op beide routes veilig — het tailnet-pad levert dan geen geldige
JWT, dus geen identiteit, en valt terug op de sleutel. De regel is korter dan ik
dacht: de header is nooit een bron, de handtekening wel.
