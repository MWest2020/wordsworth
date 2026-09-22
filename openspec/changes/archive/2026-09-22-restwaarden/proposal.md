# Change: restwaarden

> **Naschrift 2026-09-20, vóór de bouw.** De meting die dit voorstel zelf
> voorschreef ("meten vóór repareren") weerlegt de aanname waarop het rust. De
> cijfers staan in `docs/explanation/meting-restwaarden-03.md`; wat er van dit
> voorstel overeind blijft staat onderaan onder **Wat de meting ervan overliet**.
> Bouw het niet zoals het hieronder staat.

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


## Wat de meting ervan overliet (2026-09-20)

**Het webadres-geval bestaat niet zoals ik het beschreef.** De tokens in dat
document ontsleuteld: `[ORGANIZATION:521364bf]` is `Teaz` en
`[ORGANIZATION:1951231e]` is `EAZ`. De detector heeft "eazwind" nooit gevonden —
hij vond twee OCR-fragmenten van een logo. De naam in het webadres is geen
overlevende waarde maar een **nooit gedetecteerde** waarde. De voorgestelde
invariant had hier niets gevangen.

**En de invariant zelf zou schade doen.** Over 60 documenten overleven er acht
waarden. Het zijn geen namen:

```
'Oekrainers' -> 'oekrainers'    'bewoners' -> 'Bewoners'
'locatie'    -> 'Locatie'       'week 23'  -> 'Week 23'
```

Gewone woorden die de detector ten onrechte als PII zag. De invariant afdwingen
zou deze documenten weigeren of élk voorkomen van "locatie" in een token
veranderen. Allebei erger dan het gat.

**Wat de meting wél aanwijst, is het omgekeerde probleem.** Van 1125 unieke
entiteit-tokens begint 39% met een kleine letter, en daar zitten `gemeente`,
`college`, `perceel`, `naam` en `bedrijven` tussen. Er wordt te véél vervangen,
niet te weinig — en dat kost leesbaarheid op elke pagina.

**Wat overeind blijft:** het straatadres. `Industrieweg 23a` en
`Amsterdamsestraatweg 65a` staan onvervangen terwijl postcode en plaats wel
tokens zijn. Dat is een echt gat, twee keer waargenomen, en het staat los van de
rest.

**Voorstel voor het vervolg:** dit voorstel intrekken op de invariant na het
straatadres, en de over-detectie als eigen change oppakken — met `allow.json`,
dat daar precies voor bestaat en in productie nog niet eens is aangezet.


## Ingetrokken bij het archiveren (2026-09-22)

De eis **"een gepseudonimiseerde waarde staat nergens anders meer letterlijk in
het document"** is uit de delta gehaald en gaat NIET naar `openspec/specs/`.

Reden: de meting die dit voorstel zelf voorschreef weerlegde de aanname. De acht
waarden die "overleefden" waren gewone woorden (`locatie`, `bewoners`,
`week 23`) die ten onrechte als PII waren gezien, en het geval uit issue #124
bestond niet zoals beschreven — er stond `Teaz` en `EAZ`, niet `eazwind`. Die
eis afdwingen zou documenten weigeren of de tekst mangelen om een probleem op te
lossen dat er niet is.

Het staat hier en niet alleen in de git-historie omdat een ingetrokken eis die
spoorloos verdwijnt over een half jaar opnieuw wordt voorgesteld — met dezelfde
redenering en dezelfde prijs.

Wat wél naar `specs/anonymization` is gegaan: *een straat met huisnummer is een
adres* (met de Postbus-tegencase) en *een detectiewijziging wordt gemeten
voordat hij gerepareerd heet*.
