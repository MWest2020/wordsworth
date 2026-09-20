# Change: restwaarden

## Why

Issue #124, twee keer waargenomen op hetzelfde corpus:

```
[ORGANIZATION:521364bf]          <- de naam is vervangen
Industrieweg 23a                 <- het adres niet
www.eazwind.nl                   <- dezelfde naam, niet vervangen
```

en in een ander document:

> *"…een woonfunctie aan de **Amsterdamsestraatweg 65a** in `<LOCATION>`…"*

De plaatsnaam is een placeholder, het straatadres staat er gewoon. Twee van de
vijf documenten die ik bekeek droegen er een.

Dit werd zichtbaar doordat de samenvattingen die resten naar de eerste zin
tilden. Dat is geen fout van de samenvattingen — die geven de opgeslagen tekst
weer — maar het laat zien wat er gebeurt zodra iets de tekst comprimeert: een
rest die verstopt zat halverwege pagina één, staat ineens vooraan.

## De twee gevallen zijn niet hetzelfde

### 1. Het straatadres

`Industrieweg 23a` en `Amsterdamsestraatweg 65a` ontsnappen **structureel**: de
detectie vindt een postcode en een plaats, maar een straat plus huisnummer
zonder postcode niet.

In een Woo-dossier over een omgevingsvergunning is dat vaak juist hét
identificerende gegeven: het pand ís de zaak, en van een pand naar een eigenaar
is één kadasterbevraging. Dat is precies het soort gegeven waarvoor
`identifying-combinations` bestaat.

**Voorstel:** een `deny.json`-patroon voor het Nederlandse straatadres — een
woord dat op een straatachtergrond eindigt (`-straat`, `-weg`, `-laan`,
`-plein`, `-kade`, `-dijk`, `-singel`, `-hof`, `-pad`, `-gracht`, `-baan`,
`-steeg`) gevolgd door een huisnummer. Het mechanisme bestaat al
(`detection_lists.py`), het is een git-versiebeheerde wijziging door een mens,
en het staat in het auditrecord van elke de-identificatie.

Bewust géén algemeen "hoofdletterwoord + getal": dat sloopt
`Artikel 5`, `Wabo 2010` en `bijlage 3`.

### 2. Het webadres

Hier ligt het anders, en een `deny.json`-patroon op "elke URL" is het verkeerde
antwoord: `www.rijksoverheid.nl` is geen persoonsgegeven en `www.jansen-bv.nl`
wel. Een regel die beide vervangt maakt het corpus onleesbaar om een enkel geval
te vangen.

**Voorstel — de eigenschap die het onderscheid maakt:** een waarde die in dit
document is gepseudonimiseerd, hoort er nergens anders in nog letterlijk te
staan. "Eazwind" is als organisatienaam vervangen; dat diezelfde tekenreeks
binnen `www.eazwind.nl` blijft staan, is geen tweede beslissing maar een gemiste
eerste.

Dat is breder dan URL's, en dat is juist het punt: hetzelfde geldt voor een naam
in een bestandsnaam (`advies-jansen.pdf`), in een e-mailadres dat de detector
miste, of in een voettekst. Eén invariant in plaats van een lijst gevallen.

**De prijs staat in de invariant zelf:** korte waarden. Een organisatie die "De
Bank" heet, komt als tekenreeks in van alles voor. Dus een ondergrens op lengte,
en alleen op woordgrenzen — en de keuze van die ondergrens hoort gemeten te
worden op het evalcorpus, niet geraden.

## Hoe we weten of het helpt

Niet op gevoel. `gold.jsonl` kent de waarden die erin zijn gezet, dus is
meetbaar hoeveel ervan de straat overleven — vóór en na. Dat getal hoort in
`docs/explanation/` te staan naast de bestaande metingen, met de datum erbij.

Op het echte corpus (770 documenten) kan dezelfde controle niet, want daar is de
waarheid onbekend. Wat daar wél kan: tellen hoe vaak een gepseudonimiseerde
waarde nog letterlijk in zijn eigen document staat. Dat is precies de invariant
hierboven, en het is een getal dat vandaag al te meten is.

## Wat deze change niet doet

- **Geen auto-learning.** De lijsten blijven een git-wijziging door een mens,
  zoals `add-detection-feedback` het heeft neergezet.
- **Geen herverwerking van het bestaande corpus** binnen deze change. Dat is een
  aparte beslissing met een eigen prijs (770 documenten opnieuw door de straat),
  en hij hoort pas genomen te worden als bekend is hoe groot het gat is.
