---
status: accepted
last_reviewed: 2026-09-17
---

# ADR-0007: Eén token per type, ook waar een combinatie identificeert

## Context

Meting 02 telde dat **654 van de 751 documenten** in het corpus
`PERSON + DATE_TIME + LOCATION` samen dragen — 87%. De quasi-identifier is geen
randgeval hier, het is de hoofdmoot.

Dat stelde een vraag die `identifying-combinations` bewust openliet: volstaat één
token per waarde per type, of verdient een benoemde combinatie een eigen
behandeling — één gezamenlijk token voor de hele verzameling, zodat de delen niet
meer op elkaar aansluiten?

## Besluit

**Los.** Elke waarde krijgt een eigen token voor zijn eigen type. Een benoemde
combinatie wordt gemeld en gemeten, niet samengevoegd.

Besloten door Mark, 2026-09-17: *"denk los is beter"*.

## Waarom

**Samenvoegen breekt de grant.** Een grant autoriseert per type: deze ontvanger
mag `PERSON` zien en `BSN` niet. Een gezamenlijk token voor
`PERSON + DATE_TIME + LOCATION` is één waarde en kan alleen heel onthuld worden.
De hele toegangsbeslissing in dit systeem hangt aan die typegrens, en een token
dat drie typen tegelijk draagt maakt die grens onbeslisbaar.

**Samenvoegen breekt het zoeken.** Gepseudonimiseerde tekst moet doorzoekbaar
blijven — dat is de reden dat de mappingstore globaal is en één waarde overal
hetzelfde token krijgt. Drie velden in één token maakt zoeken op de postcode
alleen onmogelijk, en dan is de hele straat een dure manier om tekst onleesbaar
te maken.

**Samenvoegen zou de keuze in code leggen.** Welke combinatie identificeert,
hangt af van de populatie, de sector en de context. `identifying-combinations`
zegt dat het het oordeel van de verwerkingsverantwoordelijke is en niet van dit
project. Een engine die zelf besluit welke drie velden versmelten, neemt precies
die beslissing over — en doet dat onzichtbaar, in de uitvoer, waar niemand hem
nog terugvindt.

**De uitweg bestaat al, en is opt-in.** Wie voor een bepaalde dataset wél wil
samenvoegen, zet `mode: per_record` met een `record_key`: de geselecteerde
kolommen krijgen dan één gedeeld token. Dat is een bewuste keuze per profiel,
zichtbaar in het profiel en in de auditrecord-hash. Los is de standaard, niet de
enige mogelijkheid.

## Gevolgen

- De console en `wordsworth-measure-combinations` **melden** combinaties; ze
  grijpen niet in. Dat blijft zo.
- Het getal van 87% is daarmee geen openstaand defect maar een bekend feit over
  het corpus, met een vastgelegd antwoord op de vraag wat we ermee doen.
- Wie later toch wil samenvoegen, doet dat per profiel met `per_record` — en
  moet dan zelf verantwoorden welke combinatie hij daarvoor heeft gekozen.

## Wat dit besluit niet oplost

De combinatie blijft identificerend. Dit besluit zegt dat het systeem haar niet
uit eigen beweging verbreekt, niet dat ze onschadelijk is. Wie een corpus
publiceert waarin 87% van de documenten naam, datum en plaats draagt, heeft een
beoordeling te maken — en de meting en de console bestaan om die beoordeling
mogelijk te maken, niet om haar te vervangen.
