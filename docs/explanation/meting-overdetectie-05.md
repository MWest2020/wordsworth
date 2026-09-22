---
status: current
last_reviewed: 2026-09-21
---

# Meting 05 — wat de reprocess opleverde, en wat er niet uit te lezen valt

[Meting 04](meting-overdetectie-04.md) stelde vast wat de allow-lijst op 200
documenten terugwint. Daarna is de lijst over het hele corpus uitgerold met
`POST /reprocess`. Deze meting legt vast wat die run deed — en waarom de
voor-de-hand-liggende vergelijking "index vóór" naast "index ná" het verkeerde
antwoord geeft.

## De run

```
klaar in 43578s: {'reanonymized': 569, 'skipped': 0, 'retryable': 0, 'failed': 0}
```

569 documenten, twaalf uur, **nul mislukkingen**. Ongeveer 77 seconden per
document, vrijwel helemaal detectie. Samen met eerdere, afgebroken runs zijn
770 van de 779 documenten inmiddels onder de nieuwe lijsten ge-de-identificeerd.

## Het ene getal dat klopt

Uit de audit-records van diezelfde run, `detections.suppressed_by_list`:

| type | onderdrukte detecties |
| --- | --- |
| LOCATION | 6.085 |
| ORGANIZATION | 4.594 |
| PERSON | 2.841 |
| **totaal** | **13.520** |

Dit getal is binnen één run gemeten, onder één versie van de code, op dezelfde
tekst met en zonder de lijst. Dat is wat de lijst doet.

## Het getal dat níét klopt

De vergelijking die zich opdringt — tel de tokens vóór de reprocess, tel ze erna
— zegt iets anders:

| | eerste de-identificatie | na reprocess |
| --- | --- | --- |
| tokens geplaatst | 130.973 | 150.108 |
| PERSON | 43.937 | 32.137 |
| LOCATION | 38.813 | **66.438** |
| POSTCODE | 0 | 653 |

Er staan **19.135 tokens méér** in het corpus, terwijl de lijst er 13.520 zou
onderdrukken. Gelezen als "de lijst maakte het erger" is dat een conclusie over
de lijst. Die conclusie is fout.

## Waarom

**De basislijn is geen toestand, maar een verzameling.** De eerste
de-identificatie van deze documenten ligt in augustus (567) en september (203),
verspreid over de versies die toen draaiden. De reprocess is één versie, van één
dag. De vergelijking zet dus niet twee lijst-instellingen naast elkaar maar twee
tijdvakken, met alles wat daartussen veranderde.

Het duidelijkste bewijs staat in de tabel zelf: **geen enkel eerste record kent
het type `postcode`** (0 van 770). Die detector kwam uit
[meting 01](meting-woo-corpus-01.md) en is er ná die eerste ronde bij gekomen.
Hij vindt nu 653 postcodes die er altijd al stonden. Datzelfde geldt voor de
verdubbeling van LOCATION en de daling van PERSON: dat zijn verschuivingen in
wat de detector vindt, niet in wat de lijst weghaalt.

Het aandeel waarden dat met een kleine letter begint, steeg over diezelfde
grens van 39% naar 44%. Ook dat is geen uitspraak over de lijst.

## Maar is de detector dan grillig?

Dat was de eerste verdenking: als twee runs over dezelfde tekst niet hetzelfde
vinden, is elke voor/ná-meting zinloos. Gemeten, 20 documenten, drie keer
dezelfde tekst door `detect_entities`:

```
documenten met DRIE identieke runs: 20
documenten met verschil            : 0
detecties die niet in alle drie zaten: 0
```

De detector is **deterministisch**. De variatie zit tussen *versies*, niet
tussen *runs*. Een reprocess opnieuw draaien geeft hetzelfde; een reprocess
vergelijken met een oudere ronde vergelijkt twee instrumenten.

## Wat de lijst aan recall kost

Dat is de vraag die een allow-lijst moet verdienen, want hij haalt bescherming
wég. Gemeten op het evalcorpus (500 documenten, waar bekend is wat erin zit).
Detectie draaide **één keer** per document; de twee uitkomsten verschillen
alleen in de lijsten erachter, dus dit is niet het instrument-probleem hierboven.

| | precisie | recall | lekken |
| --- | --- | --- | --- |
| zonder lijsten | 0,391 | **0,999** | 0 |
| met lijsten | 0,404 | **0,999** | 0 |

**De recall beweegt niet.** Geen enkele ingezaaide waarde verdwijnt door de
lijst, en het aantal lekken blijft nul. De ene gemiste PERSON is in beide runs
dezelfde.

Wat wél beweegt zijn de valse positieven:

| type | fp zonder | fp met |
| --- | --- | --- |
| PERSON | 787 | **693** |
| ORGANIZATION | 808 | **758** |

144 minder verzinsels, nul minder bescherming. Dat is waar deze lijst voor
bedoeld is.

### Lees de absolute precisie hier níet als een cijfer over de detector

LOCATION, ORGANIZATION, DATE_TIME en PHONE_NUMBER hebben in dit corpus **nul**
gouden spans: alles wat de detector daar vindt telt als valse positief, ook een
correcte vondst. De precisie van 0,40 zegt dus meer over wat het corpus labelt
dan over wat de detector kan. Alleen het **verschil** tussen de twee rijen is
een uitspraak, want die twee draaiden op dezelfde detecties en hetzelfde goud.

Dat is ook waarom de allow-regels voor LOCATION hier niets doen (863 fp in
beide): de generieke termen die in het echte corpus bovenaan staan
(`bestemmingsplan`, `plangebied`) komen in deze synthetische tekst niet voor.

Zelf draaien:

```bash
python -m wordsworth.eval.pii_run gold.jsonl --lists lists
```

Zonder `--lists` meet die CLI de detectie zónder lijsten, ook op een installatie
waar ze aanstaan.

## De regel die hieruit volgt

> Een voor/ná over een reprocess heen isoleert de lijst alleen als de code
> ertussen niet veranderde. Anders meet je het verschil tussen twee versies en
> schrijft het op naam van de lijst.

Praktisch: het effect van een lijst komt uit `suppressed_by_list` in de records
van de run zelf. Dat getal is per constructie onder één versie gemeten. Wie toch
twee rondes wil vergelijken, moet eerst met de nieuwe code en de óúde lijsten
draaien — twee runs, één verschil.

## Naschrift: de deny-regel, en nog een verkeerde meter

Op 2026-09-22 draaide het corpus opnieuw, nu met de deny-regel voor het
straatadres erbij: 770 documenten, 15,4 uur, nul achterstallig daarna. De regel
voegde **3.231 straatadressen** toe, in **403 van de 770** documenten.

Dat getal komt uit de `list`-laag van het detectie-spoor van die run. Een
deny-regel schrijft zijn eigen toevoeging daar weg, dus het is per constructie
gemeten onder één versie — dezelfde discipline als `suppressed_by_list`
hierboven.

Mijn eerste poging was iets anders, en fout. Ik telde in de opgeslagen tekst het
patroon `[LOCATION:…] <getal>` — een token met een kaal getal erachter — omdat
dát het geval is dat de regel moest opheffen. Uitkomst: 100 van 400 teksten.
Dat leest als "een kwart lekt nog steeds een huisnummer", en dat is niet wat er
gemeten werd. `[LOCATION:…] 2019` is een plaatsnaam met een jaartal;
`[LOCATION:…] 3` kan een tabelregel of een artikelnummer zijn. Het patroon is
het geval niet.

Precies de valkuil die dit document beschrijft, twee secties verderop, op
dezelfde dag opnieuw ingelopen. Het onderscheid dat helpt: meet aan de
**handeling** (wat deed de laag die de wijziging is), niet aan een **vorm** in
het resultaat die ook zonder die handeling kan ontstaan.

## Nog een valkuil, uit deze meting zelf

De eerste versie van de vergelijking meldde: tweede ronde **0 tokens**, over de
hele linie. Een keurige tabel, netjes opgemaakt, volledig onzin. Oorzaak:
`anonymize` schrijft de counts op het hoogste niveau van het payload en
`reanonymize` onder een sleutel `counts`. De meting las de tweede vorm niet en
concludeerde "nul".

Een meting die nul rapporteert waar niets nul kán zijn, is een meetfout tot het
tegendeel blijkt. Dat het er geloofwaardig uitziet, is precies het probleem.
