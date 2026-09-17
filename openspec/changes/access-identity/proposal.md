# Change: access-identity

## Why

Sinds vandaag staat Cloudflare Access voor `/console`. Dat levert twee dingen op
en één probleem.

Het levert een **echte identiteit** op: een e-mailadres, per persoon, met een
sessie van acht uur. En het levert een tweede inlog op, want daarna vraagt de
console alsnog een api-sleutel.

Het probleem is dat die api-sleutel de identiteit is waarop álles verder rust.
`recipient` in een grant is een callerlabel; de console logt in als `console`.
Dat is geen persoon maar een gedeelde sleutel, en zolang dat zo is, is een
rolmodel (#80) er een op papier: "HR mag dit" betekent dan "wie de HR-sleutel
heeft mag dit", en sleutels worden gedeeld, gekopieerd en vergeten.

Er ligt dus een echte identiteit voor de deur die we niet gebruiken.

## De valkuil, en waarom die minder groot is dan ik eerst schreef

Access zet twee dingen op een verzoek: een leesbare header
`Cf-Access-Authenticated-User-Email`, en `Cf-Access-Jwt-Assertion` — een door
Cloudflare ondertekende JWT.

In #81 schreef ik dat de tailnet-route (`wordsworth-api.tail8f7877.ts.net`) dit
onbruikbaar maakt omdat daar iedereen de header kan zetten. Dat klopt voor de
**header** en niet voor de **JWT**: een handtekening vervalsen kan niet, dus wie
de JWT verifieert in plaats van de header te geloven, is op beide routes veilig.
Het tailnet-pad levert dan simpelweg geen geldige JWT, en dus geen identiteit —
en valt terug op de api-sleutel, precies zoals nu.

De regel is daarmee kort: **de header is nooit een bron, de handtekening wel.**

## Wat deze change WEL doet

- **De JWT verifiëren** tegen de publieke sleutels van het team
  (`https://raspy-wood-e123.cloudflareaccess.com/cdn-cgi/access/certs`), met een
  controle op `aud` — de applicatie heeft er een eigen
  (`320841be…e65d65`). Een JWT voor een ándere applicatie van hetzelfde team is
  geen toegang tot deze.
- **Het e-mailadres uit een geldige JWT wordt het callerlabel.** Daarmee is de
  beller een persoon en niet een sleutelbos, en staat er in het auditrecord wie
  er werkelijk keek.
- **Eén inlog.** Is er een geldige identiteit, dan vraagt de console geen
  sleutel meer.
- **De api-sleutel blijft voor alles zonder Access ervoor**: de tailnet-route,
  API-clients, `wordsworth-ingest`. Die verandert niet.

## Wat deze change NIET doet

- **Geen rollen.** Dit levert een identiteit; wat die mag is #80. De twee in één
  change stoppen betekent de autorisatiekern verbouwen terwijl je de deurbel
  vervangt.
- **Geen eigen sessies of tokens.** Access houdt de sessie; wij lezen hem.
- **Access niet verplicht stellen.** Een installatie zonder Cloudflare ervoor
  moet blijven werken zoals nu. Anders is dit niet meer soeverein te draaien, en
  dat is het hele punt van het project.

## Open vragen die deze change moet beantwoorden

1. **Wat wordt `recipient` in een grant?** Een e-mailadres, een rol, of allebei?
   Een grant op een e-mailadres is precies en onhandelbaar bij personeelswissel;
   een grant op een rol vergt #80. Mogelijk moet deze change alleen mogelijk
   maken dat het e-mailadres het callerlabel ís, en de grant-kant ongemoeid laten
   tot #80 er is.
2. ~~Wat gebeurt er met de bestaande grants op `console`?~~ **Beantwoord langs
   de rollen-beslissing (Mark, 2026-09-17): de (super)admin geeft ze opnieuw
   uit.** Zodra het callerlabel een e-mailadres wordt, heet niemand meer
   `console` en autoriseert zo'n grant niemand. Dat is geen breuk maar een
   migratiestap, en hij hoort benoemd te worden voordat hij plaatsvindt — bij de
   recipient-binding merkten we het pas achteraf.

   Concreet: bij het aanzetten van deze change worden de bestaande grants op een
   sleutellabel opgesomd, en wie ze opnieuw wil op een identiteit geeft ze
   opnieuw uit. De oude blijven staan en doen niets, precies zoals de vier
   demo-grants van augustus deden — en zichtbaar in de console, die actieve van
   ingetrokken scheidt.
3. **Waar komt de teamnaam en de `aud` vandaan?** Configuratie, ongetwijfeld —
   maar een verkeerd ingestelde `aud` is een stil gat: de JWT klopt dan wel en
   hoort bij iets anders. Fail-closed: geen configuratie is geen identiteit, geen
   waarschuwing-en-doorgaan.

## Impact

- `auth.py` (de verificatie en het label), `config.py` (team, `aud`),
  `console.py` (inlog overslaan), `openspec/specs/console`.
- Een afhankelijkheid voor JWT-verificatie, of `cryptography` (al aanwezig)
  rechtstreeks. Liever het tweede: een RS256-handtekening controleren is minder
  code dan een bibliotheek erbij, en `cryptography` staat er al voor de sleutels.
