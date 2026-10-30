---
status: not-run
last_reviewed: 2026-10-30
---

# Meting 07 — overdetectie-basislijn: vijf gewone woorden

[Meting 05](meting-overdetectie-05.md) legde vast hoe je het effect van een
lijst meet: één detectierun, twee uitkomsten erachter, nooit een vergelijking
over twee runs heen. Deze meting past dat toe op een andere klacht, uit de
coding-sessie van odin: *"Ordinary words get redacted as
ORGANIZATION/LOCATION/DATE_TIME ('statushouders', 'bewoners',
'woningcorporaties', 'juni', 'wereldvluchtelingendag')"*.

Van de vijf heeft alleen `bewoners` vandaag een regel, en die staat alleen
onder PERSON (`lists/allow.json`) — hetzelfde woord getypeerd als ORGANIZATION
of LOCATION wordt nog steeds geredigeerd, want een allow-regel werkt nooit over
typegrenzen heen. De andere vier hebben geen regel, en `allow.json` heeft geen
DATE_TIME-sectie.

Deze meting beslist niets over een allow-regel of een drempel — zie
[`design.md`](../../openspec/changes/redaction-overdetection/design.md) van de
change. Ze legt de cijfers vast waarop die beslissing straks rust.

## Status: **not run**

De basislijn draait tegen OpenAnonymiser
(`WORDSWORTH_OPENANONYMISER_URL`) — de deterministische laag heeft geen
ORGANIZATION/LOCATION/DATE_TIME-detector en kan geen van deze vijf woorden
vinden. Die live-run is een losse stap voor Mark of de coding-sessie, niet voor
de build. Dit bestand bevat daarom nu het **formaat**, niet de cijfers.

Zolang de tabellen hieronder leeg zijn, staat hier **not run**. Er komt hier
nooit een tabel die alleen de deterministische laag liet zien als was het de
basislijn — die laag vindt geen van deze vijf woorden, dus zo'n tabel zou een
ander instrument meten en het de basislijn noemen.

Zelf draaien (zie [`docs/reference/evaluation.md`](../reference/evaluation.md)):

```bash
python -m wordsworth.eval.overdetection_run gold.jsonl --lists lists \
    --out docs/explanation/meting-overdetectie-07.md
```

## Label

Elke run van dit bestand draagt deze zin, letterlijk — het heranalyseert wat
detectie NU met deze tekst zou doen, niet wat een eerdere run met andere tekst
deed (de valkuil van meting 05):

> what detection would do now on this text

## Formaat: precisie/recall/lekken/fp per type, met en zonder lijsten

| type | precisie zonder | recall zonder | fp zonder | precisie met | recall met | fp met |
| --- | --- | --- | --- | --- | --- | --- |
| _(ingevuld door de live run)_ | | | | | | |

lekken zonder lijsten: _(ingevuld door de live run)_
lekken met lijsten: _(ingevuld door de live run)_

LOCATION, ORGANIZATION, DATE_TIME en PHONE_NUMBER hebben in dit corpus geen
gouden spans (meting 05): elke vondst daar telt als valse positief. De
absolute precisie van die typen zegt dus weinig; alleen het verschil tussen
de twee kolommen, gemeten op dezelfde detecties, is een uitspraak.

## Formaat: hoe de vijf woorden vandaag getypeerd worden

Geen zin uit een document, geen gedetecteerde waarde — alleen het woord zelf
(bekend uit de coding-sessie, geen PII) en een telling per type die de
detector er vandaag aan geeft, **zonder lijsten** (de ruwe toekenning: een
lijst zou precies het type verbergen waar een toekomstige allow-regel naar
moet kijken):

| woord | telling per type |
| --- | --- |
| statushouders | _(ingevuld door de live run)_ |
| bewoners | _(ingevuld door de live run)_ |
| woningcorporaties | _(ingevuld door de live run)_ |
| juni | _(ingevuld door de live run)_ |
| wereldvluchtelingendag | _(ingevuld door de live run)_ |

## Datum

_(ingevuld door de live run)_
