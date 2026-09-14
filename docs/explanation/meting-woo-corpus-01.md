---
status: accepted
last_reviewed: 2026-09-13
---

# Meting 01 — 200 gepubliceerde Woo-documenten door de straat

De eerste keer dat wordsworth op echte documenten is gemeten in plaats van op
fixtures. Bron: `open.gelderland.nl`, opgehaald met
`scripts/eval/fetch_woo_corpus.py` (herkomst per document in `herkomst.jsonl`).

## Opzet

Woo-documenten dragen hun redactiegrond in de tekst: `[5.1.2e]` is artikel 5.1.2e
Woo, de persoonlijke levenssfeer. Elke markering staat precies waar de
publicerende overheid een persoonsgegeven heeft weggehaald. Dat is een **echt
label in een echt corpus**, gratis, zonder annotatie.

Twee kanten aan elkaar geknoopt: de gepubliceerde PDF (wat de overheid weghaalde)
en de geïndexeerde tekst (wat wordsworth daarna nog vond en liet staan). De
restcontrole gebruikt alleen checks die zónder annotatie te beoordelen zijn —
een BSN met geldige elfproef, een IBAN met geldige mod-97, een e-mailadres op een
privédomein.

## Uitkomst

| | |
|---|---|
| documenten | 200 (428 MB), 15 scans |
| eindtoestanden | **203/203 `indexed`**, nul `FAILED`, nul `UNPROCESSABLE_OCR` |
| doorlooptijd | 2 u 02 min |
| markeringen `[5.1.2e]` in de bron | **519**, verspreid over 95 documenten |
| placeholders die wordsworth plaatste | **14 526** |

Placeholders per type: ORGANIZATION 5378 · PERSON 3789 · LOCATION 3213 ·
DATE_TIME 1359 · EMAIL 634 · PHONE_NUMBER 104 · BSN 41 · IBAN 8.

**Restcontrole op de index: geen enkel persoonsgegeven van de automatisch
beoordeelbare soort.** Nul e-mailadressen, nul geldige IBANs, nul mobiele
nummers. Vier negencijferige getallen met een geldige elfproef bleken bij
inspectie geen BSN: twee btw-nummers (`BTW NL810828662B01`,
`BTW NL804306837B01`), één bestandsnaam (`D252694417_1__Overzicht…`) en één
zaaknummer van de Raad van State (`201304246/1/R6`). De detector liet ze terecht
staan — dat is precies waarom hij de elfproef gebruikt en geen kale `\d{9}`:
anders was een jurisprudentieverwijzing onleesbaar gemaakt.

## Bevinding 1 — adressen overleefden met hun identificerende helft intact

**123 volledige adressen** (straat + huisnummer + postcode) stonden ongeschonden
in de index. De NER-laag haalde de **stad** weg als `LOCATION` en liet de rest
staan:

    Burgemeester de Bordesstraat 80, 1404 GZ [LOCATION:17534a19]

Dat is de verkeerde helft. In Nederland identificeert postcode plus huisnummer
een huishouden; de stad is het mínst identificerende deel van een adres. De
straat bleef staan, het nummer bleef staan, de postcode bleef staan.

In dit corpus zijn het kantooradressen uit e-mailhandtekeningen, dus er is geen
persoonsgegeven gelekt. Het **mechanisme** is de bevinding: stond hier het
huisadres van een burger, dan was het meest identificerende deel blijven staan.

Oorzaak, en die is scherp: de taxonomie kent `ADRES`, `ADDRESS` en `POSTCODE`
(`pii_categories.py`), `normalization.py` heeft een `_postcode()`-normaliseerder
die eronder geregistreerd staat, en `legible.py` kan `[ADRES 2]` renderen — maar
**niets produceerde er ooit een**. Nul `ADDRESS`- en nul `POSTCODE`-spans in het
hele corpus. Het type was end-to-end bedraad behalve aan het begin.

Opgelost: `detectors.py` heeft nu een postcode-detector. Nagemeten op dezelfde
geanonimiseerde tekst: **67 postcodes** die nu alsnog geredigeerd worden. Een
postbus houdt zijn postcode — dat is een openbaar contactgegeven van een
organisatie, en wegredigeren maakt een besluit onleesbaar zonder iemand te
beschermen.

## Bevinding 2 — een OCR-hersteld document is niet terug te vinden op zijn bronhash

Zes documenten leken te ontbreken uit de index terwijl de Job `203/203 indexed`
meldde. Ze ontbraken niet: `recover()` schrijft de ge-OCR'de PDF weg als een
**eigen content-addressed object** en verlegt `object_key` daarheen. De originele
scan blijft bestaan, maar zijn sha256 komt niet meer in de index voor.

Geen fout — content-adressering doet precies wat hij hoort te doen. Wel een
valkuil voor iedereen die een corpus tegen de index meet: de koppeling
`sha256(bestand) → object_key` gaat niet op voor herstelde scans. De afbeelding
staat in het auditspoor, stap `ocr`, veld `old_object_key`/`new_object_key`.

## Bevinding 3 — pseudonimiseren op een combinatie van gegevens bestaat niet

Gezocht in specs, changes, code en de NORA-analyse: geen enkele vermelding van
combinaties, quasi-identifiers of k-anonimiteit. Elk gegeven wordt op zichzelf
beoordeeld.

Dat betekent dat een record als *"vrouw, geboren 1978, postcode 6541 EX,
functie X"* ongemoeid door de straat komt: geen van die vier is op zichzelf een
direct identificerend gegeven, en samen wijzen ze vaak één persoon aan. Het is
geen gap in de NORA-matrix — het staat daar niet in, want het deck noemt het ook
niet — maar het is wél een gat in de belofte.

Het raakt vooral de datasetkant (`dataset-pseudonymization`), waar kolommen per
profiel gekozen worden: precies de plek waar een combinatie ontstaat. Een eigen
change waard, niet hier binnengesmokkeld.

## Bevinding 4 — de herindexering telde haar eigen mislukkingen zonder ze aan te wijzen

De postcode-detector kwam ná de eerste meting, dus moest het corpus opnieuw door
de anonimisering. Nameting op het cluster (2026-09-14, 770 geïndexeerde
documenten): nul e-mailadressen, nul geldige IBANs, nul geldige BSN's, en **164
postcodes letterlijk in de tekst**. Daarvan staan er **56 in een
postbus-context** en blijven terecht staan; **108 moesten alsnog weg**, verspreid
over 31 documenten.

Die 56 zijn het bewijs dat de contextregel doet wat hij belooft, nu op echte
documenten in plaats van op een fixture: `Postbus 250, 6800 GD Arnhem` is het
contactadres van een overheid, geen woonadres van een mens.

Twee dingen gingen mis, en het tweede is het echte.

**De herstelactie was te duur om te draaien.** De reprocess-Job stuurde altijd
"herdraai alles": 770 documenten × ~2 min GLiNER is ruim 25 uur, voor werk van
een uur. Zo'n run wordt afgebroken — op 2026-09-13 gebeurde dat toen om 03:00 de
websocket van een `kubectl exec` wegviel. Een gate die te duur is om te draaien,
wordt niet gedraaid, en dan is het geen gate. De Job neemt nu een lijst
documenten aan.

**De gerichte run faalde, en vertelde niet waarop.** 31 documenten in 1 u 58 m:
21 gelukt, 8 retryable, 2 gefaald. De Job faalde daardoor netjes in plaats van
stil `Completed` te melden. Maar wélke tien was niet te achterhalen: het antwoord
gaf alleen tellers, en in de audit-keten stond van géén van die documenten een
regel van die dag. De keten zei dus "hier heeft nooit iemand aan gezeten" terwijl
er net tien pogingen waren gedaan. De exception werd geteld en weggegooid.

Daarmee was de enige manier om de tien terug te vinden: alle 770 opnieuw draaien
— precies de herstelactie van een dag die zojuist was weggebouwd.

Dit is dezelfde vorm als bevinding 1. Daar was een PII-type end-to-end bedraad
behalve aan het begin; hier is een run end-to-end bedraad behalve aan het eind.
De gate telt wel, maar wijst niet aan, en een mislukking zonder spoor is niet te
onderscheiden van een stap die nooit liep.

Opgelost: het antwoord noemt per document de exception-**klasse** (niet de
boodschap — die kan een fragment citeren van het document waarop hij afknapte),
en er komt een `reprocess_failed`-regel in de audit-keten met de toestand
ongewijzigd.

## Wat deze meting NIET zegt

Ze meet de pijplijn, niet de kwaliteit. **Hoeveel PII er gemist is, weet ik
niet** — daarvoor is een gelabeld corpus nodig en dat is er niet. Wat hier staat
is: van de dingen die automatisch te beoordelen zijn, is er niets blijven staan;
en van de dingen die met het oog te controleren waren, is één klasse fout
gebleken (adressen).
