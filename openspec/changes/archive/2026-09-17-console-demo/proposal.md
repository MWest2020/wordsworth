# Change: console-demo

## Why

De publieke demo laat twee dingen zien die de console niet heeft, en het zijn
precies de twee waar het gesprek over gaat:

1. **Zoeken door het corpus**, met voorgestelde termen, en resultaten met scores
   en fragmenten — het bewijs dat pseudonimiseren het zoeken niet kapotmaakt.
2. **Onthullen per rol**, met schakelaars voor de afdeling en voor de PII-types —
   het bewijs dat de sleutels rolgebonden zijn en elke onthulling in het
   auditspoor landt.

De demo doet allebei client-side, met verzonnen gegevens. Dat is eerlijk voor een
illustratie en het is ook de zwakte ervan: wie het niet gelooft, kan niets
nakijken. De console draait op het échte corpus met de échte sleutels. Daar is
dezelfde uitleg een bewijs in plaats van een animatie.

## De eis die ik hiermee herzie

`document-console` legde vast: *"The console shows the artefact, never the
original… An inspection screen that may also reveal is a second door with a
friendlier name, and it is the one nobody audits."*

Dat blijft de juiste zorg, maar ik heb hem te breed geformuleerd. Wat fout is, is
een console met een **eigen** onthulpad — eigen autorisatielogica, eigen sleutels,
een eigen route langs de grant. Wat niet fout is, is een mens die dezelfde
geauditeerde deur gebruikt met een scherm in plaats van met `curl`.

De console krijgt daarom geen eigen onthulling: de pagina roept in de browser het
bestaande `POST /documents/{id}/reveal` aan, met hetzelfde cookie, dezelfde
`authorize()`, dezelfde recipient-binding en hetzelfde auditrecord. Er komt geen
regel autorisatiecode bij. Wordt er geweigerd, dan toont het scherm de weigering
— en dát is de demonstratie: een afdeling die de sleutel niet houdt, krijgt hem
ook op een mooi scherm niet.

## Wat deze change WEL doet

- **`/console/search`** over het bestaande `/search`: voorgestelde termen,
  resultaten met score en een fragment uit de gepseudonimiseerde tekst.
- **Een onthulpaneel op de documentpagina**: de grants die voor dít document
  bestaan, met hun recipient en types. Per grant schakelaars per PII-type, want
  `reveal` accepteert al een `types`-lijst en `authorize()` snijdt die door de
  grant heen.
- **Het auditspoor van dat document**, zichtbaar onder het paneel: wie, welke
  types, wanneer — nooit de waarde.
- **JavaScript**, voor het eerst. `console-look` zei "niets te animeren"; dat
  klopte toen en klopt niet meer. Het is gewone `fetch` naar het bestaande
  eindpunt, geen framework en geen CDN.

## Wat deze change NIET doet

- **Geen grants uitgeven vanaf de console.** Dat recht ligt bij de
  issuer-labels (`harden-grant-issuer-scope`) en het console-label hoort daar
  niet bij. Zijn er geen grants, dan zegt het scherm dat, en hoe je er een maakt.
- **Geen eigen sleutels, geen eigen autorisatie, geen eigen audit.**
- **Geen waarden in het auditoverzicht.** Het spoor zegt welke types, niet wat.

## Impact

- `console.py`, `templates/`, `static/console.js` (nieuw),
  `openspec/specs/console` (één MODIFIED, twee ADDED).
