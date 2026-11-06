---
status: not-run
last_reviewed: 2026-11-06
---

# Meting 08 — de particle-regel als laag in de overdetectie-basislijn

Vervolg op [meting 07](meting-overdetectie-07.md): dezelfde basislijn, nu met
`dutch_particle_name` als derde laag naast `deterministic` en
`openanonymiser`. De change `particle-names-measured` bestaat omdat
`eval/pii_run.py` en `eval/overdetection_run.py` de particle-regel
(`particle-names-rule`) voorheen niet konden zien: zonder een laag ervoor was
"voor en na" door constructie identiek.

De basislijn draait tegen OpenAnonymiser (`WORDSWORTH_OPENANONYMISER_URL`);
zie [meting 07](meting-overdetectie-07.md) voor waarom de deterministische
laag — en nu ook de particle-laag — dit niet kunnen vervangen: geen van beide
heeft een ORGANIZATION/LOCATION/DATE_TIME-detector.

Zelf draaien:

```bash
python -m wordsworth.eval.overdetection_run gold.jsonl --lists lists \
    --layers deterministic,openanonymiser,dutch_particle_name \
    --out docs/explanation/meting-overdetectie-08.md
```

## Status: **not run**

Gemeten op 2026-11-06: in deze build-omgeving was de service niet bereikbaar
(`httpx.ConnectError: Connection refused` op de health-check). De echte
uitvoer van het commando hierboven, letterlijk en ongewijzigd:

```
layers: deterministic,openanonymiser,dutch_particle_name

**what detection would do now on this text**

not run: OpenAnonymiser was unreachable.
```

Zolang dat zo is, staat hier **"not run"** — nooit een tabel die alleen de
deterministische en de particle-laag laat zien als was dat de basislijn.

## Wat deze derde laag toevoegt

`dutch_particle_name` matcht alleen `<voornaam uit de gazetteer> <partikel>
<achternaam>`. Op de vijf woorden van meting 07 (`statushouders`, `bewoners`,
`woningcorporaties`, `juni`, `wereldvluchtelingendag`) verandert hij niets,
want geen van die woorden heeft die vorm. Het enige effect op déze basislijn
is een eventuele extra PERSON-detectie op een naam die al als partikelnaam in
het fixture-corpus voorkomt (`Janine van Dijk`,
`tests/fixtures/pii_gold_synthetic.jsonl`) — en die naam heeft al een regel
onder PERSON in `lists/allow.json`.

## Los daarvan: wat deze laag op de PII-evaluatie doet

Op een los gebouwde set van tien namen waarvan de voornaam niet in de
gazetteer zit (`docs/reference/evaluation.md`, sectie "The `dutch_particle_name`
layer"), scoort `dutch_particle_name` alleen 0 van 10: de regel is verankerd
op de gazetteer en kan een voornaam die er niet in staat per definitie niet
vinden. Dat getal staat in dat andere document, niet hier — deze pagina blijft
bij de overdetectie-basislijn.

## Twee dingen die deze meting niet beweert

Elk een losse, volledig Engelse zin, de vaste bewoording uit de change:

Recall on real documents is unknown.

The Gooise Meren miss is not closed by this change.

In het Nederlands: deze meting zegt niets over de recall op echte, nog niet
eerder geanonimiseerde documenten, en document `1c87f856` uit het pilotrapport
(wordsworth #284) houdt zijn leesbare naam totdat
`reanonymise-particle-name-documents` het herverwerkt.

## Formaat: precisie/recall/lekken/fp per type, met en zonder lijsten

| type | precisie zonder | recall zonder | fp zonder | precisie met | recall met | fp met |
| --- | --- | --- | --- | --- | --- | --- |
| _(ingevuld door de live run)_ | | | | | | |

lekken zonder lijsten: _(ingevuld door de live run)_
lekken met lijsten: _(ingevuld door de live run)_

## Formaat: hoe de vijf woorden vandaag getypeerd worden

| woord | telling per type |
| --- | --- |
| statushouders | _(ingevuld door de live run)_ |
| bewoners | _(ingevuld door de live run)_ |
| woningcorporaties | _(ingevuld door de live run)_ |
| juni | _(ingevuld door de live run)_ |
| wereldvluchtelingendag | _(ingevuld door de live run)_ |

## Datum

2026-11-06, build-omgeving zonder bereikbare OpenAnonymiser-service.
