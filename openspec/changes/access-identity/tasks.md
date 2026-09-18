# Tasks

Gebouwd. Vraag 2 was beantwoord langs de rollen-beslissing: de (super)admin
geeft de bestaande grants opnieuw uit op een identiteit. Wat deze change doet is
ze **benoemen vóór de omschakeling**.

## 1. De verificatie
- [x] RS256-verificatie tegen `/cdn-cgi/access/certs` van het team, met `aud`
      en `exp`. Liever met `cryptography` (staat er al) dan met een nieuwe
      afhankelijkheid: een handtekening controleren is minder code dan een
      bibliotheek erbij.
- [x] De sleutels cachen met een korte houdbaarheid; Cloudflare rouleert ze.
      Een mislukte verversing is geen reden om een oude sleutel eeuwig te
      vertrouwen, en ook geen reden om iedereen buiten te zetten — dat verschil
      moet in de code staan en niet in de hoop.
- [x] Geen configuratie = geen identiteit. Fail-closed, en niet
      waarschuwen-en-doorgaan.

## 2. Het label
- [x] Een geldige identiteit wordt de caller in `scope["state"]`, waar het
      api-sleutel-label nu komt. Eén beslispunt, nu drie transportvormen:
      header, cookie, en een geverifieerde assertie.
- [x] De console slaat het sleutelformulier over als er al een identiteit is.

## 3. Wat er NIET verandert
- [x] De tailnet-route en API-clients houden hun sleutel. Een installatie zonder
      Cloudflare ervoor werkt ongewijzigd — anders is dit niet meer soeverein te
      draaien, en dat is het hele punt.

## 4. Bewijs
- [x] Een test die een verzoek mét `Cf-Access-Authenticated-User-Email` en
      zónder geldige JWT géén identiteit geeft. Dat is de kern.
- [x] Een test met een geldig ondertekende JWT voor een ándere `aud`.
- [x] Een test dat het auditrecord de persoon noemt en niet het sleutellabel.
- [x] Live: inloggen via Access en kijken of het auditspoor een e-mailadres
      toont in plaats van `console`.

## De correctie op het issue
In #81 schreef ik dat de tailnet-route dit onbruikbaar maakt omdat daar iedereen
de header kan zetten. Dat geldt voor de header en niet voor de JWT: een
handtekening is niet te vervalsen. Wie de JWT verifieert in plaats van de header
te geloven is op beide routes veilig — het tailnet-pad levert dan geen geldige
JWT, dus geen identiteit, en valt terug op de sleutel. De regel is korter dan ik
dacht: de header is nooit een bron, de handtekening wel.

## Wat het bouwen erbij leerde

**De correctie uit het voorstel hield stand, en werd scherper.** Ik dacht eerst
dat de tailnet-route SSO onbruikbaar maakte omdat daar iedereen de header kan
zetten. Dat geldt voor de header en niet voor de handtekening — en de test die
dat vastlegt is `test_the_readable_header_is_never_a_source`: een verzoek mét
`Cf-Access-Authenticated-User-Email` en zónder geldige JWT levert **niets** op.

**Met echte sleutels getekend, niet met een dubbel dat "geldig" zegt.** De hele
belofte is dat een handtekening niet te vervalsen is; een stub die `True`
teruggeeft bewijst daar niets over. Dus: een echt RSA-paar, een echte
handtekening, en tests die geknoei met de payload, `alg: none`, een andere `aud`,
een andere issuer, een verlopen assertie en een onbekende sleutel elk apart
afwijzen.

**Een sleutelverversing die faalt mag niemand buitensluiten.** De provider
rouleert zijn sleutels, dus ze worden vijftien minuten gecacht. Faalt het
ophalen, dan houden we wat we hebben: een assertie die we nog kunnen verifiëren
is niet minder betrouwbaar omdat een netwerkaanroep eruit lag. Hebben we
helemaal niets, dan weigert de lege verzameling alles — dat is de veilige kant.

## Nagemeten
- 637 tests groen, waarvan 21 nieuw.
- De kern, end-to-end: een onthulling met een geverifieerde assertie landt in het
  auditrecord als `mark@westerweel.work` en niet als `console`. En dezelfde
  grant geweigerd (403) aan wie binnenkomt met de console-sleutel — anders was
  de identiteit versiering.

## Bij het uitrollen
- [ ] `wordsworth-access-preflight` draaien en de uitkomst aan Mark laten zien
      vóórdat `WORDSWORTH_ACCESS_TEAM_DOMAIN` en `WORDSWORTH_ACCESS_AUD` in de
      configmap komen.
- [ ] De demo-grant staat op `console` en wordt inert; opnieuw uitgeven op een
      e-mailadres is Marks keuze, niet die van dit commando.
