---
status: current
last_reviewed: 2026-09-20
---

# Meting 03 — wat er van de pseudonimisering overblijft

Uitgevoerd op 2026-09-20 tegen de draaiende productie-index, op 60 documenten
uit het Woo-corpus, naar aanleiding van issue #124 en het voorstel
`restwaarden`. **De uitkomst weerlegt de aanname waarop dat voorstel rustte.**

## Wat ik dacht te gaan vinden

Issue #124 begon met deze waarneming:

```
[ORGANIZATION:521364bf]          <- de naam is vervangen
www.eazwind.nl                   <- dezelfde naam, niet vervangen
```

Daaruit leidde ik af: een gepseudonimiseerde waarde overleeft elders in
hetzelfde document als deelstring. Het voorstel `restwaarden` stelde
vervolgens een invariant voor die dat zou verbieden.

## Wat er werkelijk staat

De tokens in dat document ontsleuteld:

| token | waarde |
| --- | --- |
| `[ORGANIZATION:521364bf]` | `Teaz` |
| `[ORGANIZATION:1951231e]` | `EAZ` |

**De detector heeft "eazwind" nooit gevonden.** Hij vond twee *fragmenten* —
`Teaz` en `EAZ` — in de OCR van wat vermoedelijk een logo is. De naam in het
webadres is dus geen overlevende waarde maar een nooit gedetecteerde waarde.
De voorgestelde invariant had hier niets gevangen.

## De invariant zelf, gemeten

Over 60 documenten, alle entiteit-tokens ontsleuteld en teruggezocht in de
gepseudonimiseerde tekst (woordgrenzen, lengte ≥ 4):

| | |
| --- | --- |
| documenten met een "overlevende" waarde | **7 van 60** |
| overlevende waarden | 8 |
| waarvan in dezelfde schrijfwijze | 3 |
| waarvan alleen in een andere schrijfwijze | 5 |

En dit zijn ze:

```
'Oekrainers'   -> 'oekrainers'
'bewoners'     -> 'Bewoners'
'locatie'      -> 'Locatie'
'week 23'      -> 'Week 23'
'deze locatie' -> 'Deze locatie'
```

Geen namen. **Gewone Nederlandse woorden die de detector ten onrechte als PII
zag.** Had ik de voorgestelde invariant gebouwd, dan had hij deze documenten
geweigerd of elk voorkomen van "locatie" en "bewoners" in een token veranderd.
Allebei erger dan het gat dat hij moest dichten.

## Waar het wél op wijst

Dezelfde 60 documenten, 1125 unieke entiteit-tokens (BSN/IBAN/e-mail/postcode
niet meegeteld — die komen van de deterministische laag):

| | |
| --- | --- |
| waarde begint met een **kleine letter** | **435 (39%)** |
| per type | LOCATION 134, ORGANIZATION 136, PERSON 92, DATE_TIME 73 |

Een greep uit die 435:

```
LOCATION      'gemeente'      LOCATION      'locatie'
LOCATION      'perceel'       ORGANIZATION  'college'
ORGANIZATION  'bedrijven'     ORGANIZATION  'asielzoekers'
PERSON        'naam'          ORGANIZATION  'uw college'
```

Niet alle 435 zijn fout — `naarden` en `gooisemeren` zijn echte plaatsnamen die
de OCR met een kleine letter afleverde. Maar `gemeente`, `college`, `perceel`,
`naam` en `bedrijven` zijn geen persoonsgegevens, en ze worden wél vervangen.

**Dat is het echte probleem in dit corpus**, en het is het tegenovergestelde van
wat ik voorstelde te repareren: niet te weinig vervangen maar te veel. Het kost
leesbaarheid op elke pagina, het blaast het aantal tokens op, en het maakt de
demo slechter dan het systeem is.

## Wat hiervan overeind blijft

Het **straatadres**. `Industrieweg 23a` en `Amsterdamsestraatweg 65a` staan
onvervangen in de tekst terwijl postcode en plaats wel tokens zijn. Dat is een
echt detectiegat, twee keer waargenomen, en het staat los van alles hierboven.

## De les

Ik had een waarneming, ik verzon er een verklaring bij, en ik schreef een spec
op die verklaring — inclusief een invariant met tests. De verklaring was fout,
en dat was met één ontsleuteling te zien geweest.

`restwaarden` zei zelf "meten vóór repareren". Dat die regel erin stond, is de
enige reden dat dit op tijd boven kwam.
