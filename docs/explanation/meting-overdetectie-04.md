---
status: current
last_reviewed: 2026-09-20
---

# Meting 04 — hoeveel de allow-lijst terugwint

Vervolg op [meting 03](meting-restwaarden-03.md), die vaststelde dat 39% van de
entiteit-tokens een waarde heeft die met een kleine letter begint. Deze meting
beantwoordt de vervolgvraag: **wat wint een handgemaakte allow-lijst daarvan
terug, en waar houdt het op?**

Gemeten op 2026-09-20 tegen de draaiende productie-index, 200 documenten.

## Wat de lijst doet

| lijst | unieke tokens onderdrukt | **voorkomens in de tekst** |
| --- | --- | --- |
| 35 regels (eerste opzet) | 32 van 5374 (1%) | 1640 van 34895 (**5%**) |
| 62 regels (uitgebreid) | 59 van 5374 (1%) | 3511 van 34895 (**10%**) |

Het verschil tussen die twee kolommen is de hele reden dat dit werkt. Een
generiek woord is één token en staat honderd keer op de pagina; een naam is één
token en staat één keer. Een lijst van 62 regels raakt 1% van de tokens en 10%
van wat een lezer ziet.

## Waar de kandidaten vandaan kwamen

Niet uit intuïtie. De vaakst voorkomende waarden die met een kleine letter
beginnen, geordend op hoe vaak ze in de tekst staan:

```
378  LOCATION      'naarden'            145  LOCATION      'inrichting'
159  LOCATION      'gemeente Gooise…'   123  ORGANIZATION  'bedrijfswoning'
111  LOCATION      'bestemmingsplan'     93  LOCATION      'plangebied'
```

Die lijst is de **generator**, niet de beslisser. Elke regel is daarna een
menselijk oordeel, met de reden in het bestand.

## Twee dingen die de meting aan het licht bracht

**1. `gemeente Gooise Meren` wordt als `LOCATION` gedetecteerd, niet als
`ORGANIZATION`.** De regel stond alleen onder ORGANIZATION en 159 voorkomens
bleven daardoor staan. Getypeerde regels zijn echt getypeerd: een waarde die de
detector wisselend typeert, heeft onder beide types een regel nodig.

**2. Frequentie kan het criterium niet zijn.** `naarden` staat met 378
voorkomens bovenaan en is een échte plaatsnaam, die de OCR met een kleine letter
afleverde. Hij staat er daarom **niet** op. De lijst bevat woorden die geen naam
zíjn; hij bevat geen namen die toevallig grof zijn.

## Waar het ophoudt

Na 62 regels is de staart wat hij is: losse OCR-fragmenten die één keer
voorkomen. Nog honderd regels erbij zou de tabel hierboven nauwelijks bewegen.
Wat daar wél helpt is betere OCR of een betere detector, en dat is een ander
gesprek dan een lijst.

## De rem

Elke regel wordt in CI getoetst tegen het evalcorpus, waar bekend is wat er aan
PII in zit. Een regel die een ingezaaide waarde onderdrukt, faalt — en dat geldt
ook voor de **losse woorden** van zo'n waarde. Het corpus zaait volledige namen
("Hendrik de Vries"), maar de detector levert in de praktijk ook losse
achternamen, en een regel `^vries$` is precies het gevaarlijke geval.

Mijn eerste versie van die toets keek alleen naar de volledige waarde en liet
dat passeren. Dat is gecontroleerd door de regel er tijdelijk in te zetten.
