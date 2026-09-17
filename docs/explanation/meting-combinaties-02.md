---
status: draft
last_reviewed: 2026-09-17
---

# Meting 02 — combinaties in het echte corpus

Meting 01 liep op 31 documenten en noemde de quasi-identifier als bevinding 3,
zonder getal. Dit is dat getal, op de 751 documenten die er werkelijk in staan.

Gemeten op 2026-09-17, in het cluster, op `document_pseudonyms` — de tokens die
de pijplijn zelf heeft gemunt. Niet op een herdraai van de detectoren over de
brontekst: dat beantwoordt "wat zouden de detectoren vandaag zeggen", en dat is
een andere vraag dan "wat heeft de straat gedaan".

## Wat het corpus draagt

| type | documenten |
| --- | ---: |
| ORGANIZATION | 730 |
| LOCATION | 717 |
| PERSON | 706 |
| DATE_TIME | 704 |
| EMAIL | 476 |
| PHONE_NUMBER | 341 |
| POSTCODE | 326 |
| BSN | 68 |
| IBAN | 34 |

## Wat er samen in staat

| combinatie | documenten |
| --- | ---: |
| `PERSON + LOCATION` | 677 |
| `PERSON + DATE_TIME + LOCATION` | 654 |
| `BSN + PERSON` | 66 |

**654 van de 751 documenten** — 87% — dragen een naam, een datum en een plaats
in hetzelfde document. Dat is de combinatie waar dertig jaar heridentificatie-
onderzoek over gaat, en ze staat hier in bijna alles.

## Wat dit getal wél zegt

Dat de combinatie *aanwezig* is, in bijna het hele corpus. Wie zou beweren dat
"er staan geen namen in" volstaat, wordt hier tegengesproken door de telling:
zelfs als je de namen weghaalt blijft datum-plus-plaats staan, en andersom.

Het zegt ook dat het geen randgeval is dat je later wel oppakt. 87% is de
hoofdmoot.

## Wat dit getal níet zegt

**Niet dat elk van die 654 een persoon aanwijst.** Dat hangt af van hoeveel
mensen dezelfde combinatie delen, en dat vergt een populatiebestand dat dit
systeem niet heeft. Een verzonnen k leest als degelijkheid en is erger dan geen
k. Zie [identifying-combinations](../../openspec/specs/pii-categories/spec.md):
het systeem meldt combinaties, het beoordeelt ze niet.

**Niet dat de types kloppen.** Ze komen uit de detectielaag, met de
foutenmarge die daarbij hoort. `LOCATION` is bij een gemeentelijk besluit vaak
de gemeente zelf — geen persoonsgegeven. Dat is precies waarom het scherm bestaat
en waarom de vaststelling bij een mens ligt.

**Niet dat er nu iets kapot is.** Al deze types zijn in de opgeslagen tekst al
gepseudonimiseerd; ze zijn hier geteld aan hun tokens. De vraag die dit getal
stelt is een andere: of één token per type genoeg is, of dat de combinatie ook
als geheel een eigen behandeling verdient.

## Het antwoord op de vraag die dit getal stelt

Beantwoord door Mark op 2026-09-17: **los**. Eén token per waarde per type; een
benoemde combinatie wordt gemeld en gemeten, niet samengevoegd. Samenvoegen zou
de per-type-grens breken waar elke grant aan hangt, het zoeken onmogelijk maken,
en de keuze wélke combinatie identificeert in de code leggen. Zie
[ADR-0007](adr/0007-one-token-per-type.md).

## Hoe het na te rekenen

```bash
wordsworth-measure-combinations declaraties.json
```

of, met het oordeel op de plek waar iemand de documenten leest: `/console/combinations`.
