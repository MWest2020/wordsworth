# Change: console-look

## Why

De console werkt en ziet eruit als een testpagina. Mark, na het eerste bezoek:
*"dit is een beetje.... rudimentair"*.

Dat is geen smaakkwestie. Dit scherm is het demo-oppervlak waarmee wordsworth
wordt uitgelegd aan mensen die het verschil tussen een token en een naam nog
moeten zien. Er bestáát al een ontwerp voor precies dat gesprek — de publieke
demo (`MWest2020/wordsworth-demo`) — met een eigen palet, drie families en een
tokenchip die al doet wat dit scherm nodig heeft. Twee verschillende uiterlijken
voor hetzelfde verhaal is een gemiste gelegenheid en, erger, het laat het
werkende ding er minder af uitzien dan de illustratie ervan.

## Wat deze change WEL doet

- **Hetzelfde ontwerp als de demo.** Dezelfde CSS-variabelen (licht én donker),
  dezelfde families, dezelfde `.tok`, `.card` en `.panel-head`. Overgenomen, niet
  opnieuw bedacht.
- **De lettertypen worden hier gehost.** De demo haalt ze bij Google; dit scherm
  serveert ze zelf uit `/console/static`. Negen latijnse faces, 224 KB.
- **De statische map is auth-vrij**, als subtree. De inlogpagina is zelf auth-vrij
  en een inlogscherm dat zonder zijn letters rendert is een kapotte deur.

## Wat deze change NIET doet

- **Geen nieuwe functionaliteit.** Dezelfde pagina's, dezelfde gegevens,
  dezelfde grenzen. Alleen de presentatie.
- **Geen JavaScript.** De demo heeft animaties omdat hij een verhaal vertelt;
  dit scherm toont wat er werkelijk in de database staat en heeft niets te
  animeren.
- **Geen CDN, ook niet voor het gemak.** Een soevereiniteitsdemo die zijn letters
  bij Google ophaalt, weerlegt zichzelf in de netwerkinspector — en dit is het
  scherm waar mensen juist gaan kijken.

## Impact

- `templates/` (alle vier), `static/` (nieuw), `auth.py` (subtree-vrijstelling),
  `api.py` (de mount), `console.py`, `openspec/specs/console`.
