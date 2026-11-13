---
status: current
last_reviewed: 2026-11-13
---

# Onderwerpen van een dossier

Een onderwerp is een **groep documenten binnen één dossier**, met een naam uit de
termen die die groep onderscheiden van de rest van hetzelfde dossier.

**Een onderwerp versmalt het zoeken en raakt de rangschikking niet.** Dat
documenten op elkaar lijken zegt niet dat ze allebei antwoord geven op de vraag
die iemand stelt. Het filter staat daarom naast de zoekvraag en nooit erin — in
`bool.filter` voor de lexicale helft, ín de `knn`-clause voor de vectorhelft
(zie `docs/how-to/index-mapping.md` voor waarom dat verschil ertoe doet).

## Berekenen

```sh
curl -XPOST $API/dossiers/<dossier-uuid>/topics -H "x-api-key: $KEY"
```

Of in de console: **onderwerpen** → dossier kiezen → *Bereken onderwerpen*.

Op verzoek en niet bij het inlezen. Eén document laat geen onderwerpen zien, en
bij elk binnengekomen document het hele dossier herberekenen is werk dat
kwadratisch groeit voor een antwoord dat op dat moment niemand leest.

Een berekening **vervangt** de vorige. Twee generaties naast elkaar levert een
lijst op waarvan niemand weet welke helft nog klopt.

## Het antwoord lezen

```json
{
  "dossier_id": "…",
  "topics": [{"id": "…", "name": "vergunning · dakkapel · welstand",
              "computed_name": "vergunning · dakkapel · welstand",
              "given_name": null, "computed_at": "2026-09-19T…",
              "document_count": 41}],
  "seen": 120, "with_vector": 118, "without_topic": 9,
  "distance": 0.45, "min_size": 3
}
```

| veld | betekenis |
| --- | --- |
| `seen` | documenten van dit dossier in de index |
| `with_vector` | daarvan met een embedding; zonder vector kan een document niet meedoen |
| `without_topic` | documenten die in geen groep terechtkwamen |
| `distance` | de hoogte waarop de boom is doorgesneden — gevónden, niet gekozen |
| `max_share` | geen onderwerp mag groter zijn dan dit deel van het dossier |
| `min_size` | kleiner dan dit is geen onderwerp maar een toevalligheid |

Die getallen staan er omdat een lijst van vier onderwerpen over 118 documenten
anders leest als een uitspraak over alle 120.

`GET /dossiers/<id>/topics` geeft wat er bij de laatste berekening uitkwam,
zónder `seen`/`with_vector`/`without_topic` — die bestaan alleen in het antwoord
van de berekening zelf. Geen onderwerpen betekent: nog niet berekend.

## Zoeken binnen een onderwerp

```sh
curl "$API/search?q=dakkapel&dossier=gooise-meren-woo-2022&topic=<topic-uuid>"
```

`topic` versmalt binnen de `dossier`-scope. De documenten die overblijven staan
onderling in dezelfde volgorde als zonder het onderwerp.

Dit blijft werken na een `/reprocess`: die herindexeert de tekst en de vector,
maar geeft het onderwerp-lidmaatschap terug aan de nieuwe `index()`-aanroep, dus
een document valt er niet stilzwijgend uit.

## Hoeveel groepen, en waarom niet een vast getal

De eerste versie knipte op een vaste cosinusafstand van 0.45. Op het eerste
echte corpus (Gooise Meren, 567 documenten) gaf dat **één groep van 443** — 78%
van het dossier — met de naam "zoals · gebruik · waar". Gemeten over hetzelfde
corpus:

| afkapafstand | grootste groep |
| --- | --- |
| 0.45 | 78% |
| 0.30 | 62% |
| 0.20 | 50% |
| 0.15 | 24% |

Een vast getal is dus geen eigenschap van de wereld maar van één corpus.
Bestuurlijke stukken lijken sterk op elkaar; op een ander corpus staat de goede
waarde ergens anders.

De eigenschap die je wél wilt, is direct op te schrijven: **geen enkel onderwerp
mag het dossier zijn.** De boom wordt daarom doorgesneden op de hoogtes die hij
zélf heeft, en gezocht wordt de hóógste snede waarbij geen groep groter is dan
`max_share` (standaard 25%). Grof is goed, zolang het antwoord op "waar gaat dit
over" niet "hier gaat het over" is.

### Kleine dossiers

Bij tien documenten mag een groep hoogstens 2,5 documenten hebben (25%) én moet
hij er minstens 3 hebben (`min_size`). Die twee regels sluiten elkaar uit, en
het antwoord werd **"geen onderwerpen"** — vijf van de tien dossiers in
productie kregen dat, niet omdat ze geen onderwerpen hebben maar omdat de regels
elkaar opheffen.

Is het aandeel op dit dossier onhaalbaar, dan geldt het niet, en blijft de eis
over waar het echt om gaat: **meer dan één groep.** Eén groep die alles is, is
geen indeling; twee groepen van vijf in een dossier van tien is dat wel.

## Namen

De berekende naam bestaat uit de drie meest onderscheidende termen (TF-IDF over
het dossier: vaak in deze groep, zeldzaam daarbuiten), met één eis erbij: **een
term moet de groep vertegenwoordigen, niet één document erin** (minstens twee
documenten en minstens 30% van de groep).

Zonder die eis kiest TF-IDF met voorliefde OCR-ruis. Een scanfout staat in
precies één document en nergens anders in het dossier, en scoort daarmee
maximaal onderscheidend. Het eerste echte corpus gaf namen als
`2anleg · aannemersbedrif · aannemersbedtif` — drie spellingen van hetzelfde
woord, geen van alle een onderwerp.

Twee eisen erbij, allebei gemeten op datzelfde corpus:

- **een naam bestaat uit woorden**: minstens vier letters, geen cijfers. Dat
  haalt `81in`, `egeee2`, `1485m`, `ddl4` en `12112018pdf` eruit — scanfouten en
  bestandsnamen;
- **en de term is niet corpuszeldzaam**: minstens 1% van het dossier (met een
  bodem van 3 documenten). De idf-helft van TF-IDF beloont zeldzaamheid, en een
  scanfout is het zeldzaamste wat er is.

Wat er dan overblijft, op hetzelfde corpus:

    avondperiode · bedrijfsduur · berekeningswijze
    informatiebijeenkomst · nieuws · noodoproep
    telefoonnummer · vooraf · precaire

De grootste groep houdt een vlakke naam (`vastgesteld · genoemde · geval`). Dat
is geen fout in de naamgeving maar een eigenschap van die groep: hij ís
heterogeen bestuurlijk proza. Een naam die dat verbergt zou slechter zijn. Dezelfde vorm die `zeef`
onder `--no-llm` gebruikt, en om dezelfde reden: een door een taalmodel bedachte
titel is een bewering waarvan niemand de herkomst kan navertellen, en dit
systeem verwerkt persoonsgegevens.

**Pseudonym-tokens komen nooit in een naam.** Onderwerpen worden berekend over
gepseudonimiseerde tekst, dus een onderscheidende term kán `[PERSOON:3fa9c2d1]`
zijn — en een onderwerpnaam belandt op schermen, in exports en in URL's, waar de
reveal-gate nooit kijkt. De tokens gaan eruit vóór het tokeniseren
(`pseudonymizer.without_tokens`), niet erna: anders valt een token uiteen in
"persoon" en "3fa9c2d1" en staat de helft er alsnog in. Bewaakt door
`test_a_token_never_becomes_part_of_a_name`.

### Alleen zelfstandige naamwoorden

TF-IDF kiest een term op frequentie, niet op woordsoort. Op het 415-documenten
pilotdossier zag Mark namen als `iedereen · ruil · steunt`, `overeen · recente
· volgen` en `besloot · harte · nabijheid` — een voornaamwoord, werkwoorden,
een bijvoeglijk naamwoord en de naamwoordhelft van een vaste uitdrukking ("van
harte"), geen van alle een onderwerp.

Gemeten op die 33 woorden, 2026-10-31:

- **Een algemeen-Nederlandse frequentiedrempel (wordfreq Zipf) scheidt ze
  niet.** "harte" (4,42) is gangbaarder dan "duurzaamheid" (4,14), maar
  "veiligheid" (4,96) is gangbaarder dan allebei.
- **Een los woord taggen is fout.** spaCy `nl_core_news_sm` tagt
  "vergadertijd" los als ADJ en "rondvraag" los als ADV.
- **Getagd in hun eigen zin, matchen zelfstandige naamwoorden die geen deel
  zijn van een vaste uitdrukking elk oordeel dat Mark gaf.**

Daarom benoemt een term alleen mee waar hij in zijn zin een zelfstandig
naamwoord is (`NOUN` of `PROPN`) én niet de afhankelijkheid `fixed` heeft (de
vaste-uitdrukking-relatie — "harte" in "van harte"). De tagging draait op de
documenttekst met de pseudonym-tokens er al uit (`without_tokens`), tot
hoogstens de eerste 20.000 tekens per document: een onderwerp komt uit wat een
groep deelt, en een afkap per document verandert niet welke termen een groep
gemeen heeft.

Het model is de Nederlandse spaCy-pipeline `nl_core_news_sm`, gepind op versie
3.8.0 en geïnstalleerd in het image — de cluster haalt er tijdens het draaien
niets bij op. spaCy zelf is MIT; het model is CC BY-SA 4.0 (getraind op
Universal Dependencies Dutch Alpino en LassySmall), ongewijzigd gebruikt en
niet opnieuw verspreid. Attributie staat in `NOTICE`.

### Geen twee onderwerpen met dezelfde naam

Twee groepen kunnen hetzelfde topdrietal scoren — `zaal · vergadertijd ·
rondvraag` kwam in het pilotdossier voor twee verschillende onderwerpen voor.
Na het berekenen van elke naam wijkt de latere in weergavevolgorde uit: de
laatste term van zijn naam wordt vervangen door de volgende scorende term die
nog niet in de naam zit, zodat de eerste twee termen blijven staan. Is er geen
volgende term meer, dan komt er " (2)" achter — want twee groepen zonder enig
verschil in hun termen zijn ook geen onderscheiden onderwerp, en dat mag niet
onzichtbaar blijven.

Hernoemen:

```sh
curl -XPATCH $API/topics/<topic-uuid> -H 'content-type: application/json' \
  -d '{"name":"Kapvergunningen 2022"}'
```

De berekende naam blijft staan. Een lege naam haalt de gegeven naam weer weg.

## Labels van het taalmodel

De berekende naam zegt welke woorden vaak zijn, niet waar een groep over gaat
(`onderdeel · verder · krijgen`). Daarom kan een onderwerp daarnaast een
**label** krijgen: hoogstens zes woorden en één zin uitleg, geschreven door het
taalmodel in het cluster (Ollama, `WORDSWORTH_LLM_MODEL`). Change
`topic-labels-llm`.

**Wat het model ziet.** Per onderwerp de opgeslagen samenvattingen van de
hoogstens acht leden die het dichtst bij het zwaartepunt van de groep liggen
(vectoren uit de zoekindex), plus de termen van de berekende naam. Alles
gepseudonimiseerd; er gaat geen opgeslagen tekst en geen onthulde waarde heen.
Heeft geen van die acht een samenvatting, dan wordt het model niet aangeroepen
en telt het onderwerp als `no_summaries`: maak eerst de samenvattingen
([samenvattingen.md](samenvattingen.md)).

**Een label is een bewering van een model**, net als een samenvatting. Het
staat in `topics.llm_label` en `llm_description`, met `llm_model` en `llm_at`,
en de console toont het met "geschreven door `<model>` op `<datum>`" en de
termen eronder. Het vervangt de berekende naam niet; die blijft staan. Wat
een mens ziet: de naam die een mens gaf (`PATCH /topics/{id}`), anders het
label, anders de termen (`topics.display_name`). Overal waar die naam het
label is, staat erachter "(taalmodel, geschreven door `<model>` op `<datum>`)":
op de onderwerpenpagina, de dossierpagina en in het zoekfilter
(`topic_claim.claim`). `GET /dossiers/{id}/topics` geeft `llm_label`,
`llm_description`, `llm_model` en `llm_at` bij elk onderwerp.

**Wat wordt afgewezen** (`topic_label_check.py`). Een label van nul of meer
dan zes woorden of meer dan 80 tekens; een beschrijving die leeg is, meer dan
één regel heeft of langer is dan 200 tekens; en in allebei:

- tekst die verandert onder NFKC of door het weghalen van onzichtbare tekens
  (Unicode-categorie Cf, zoals een zero-width space);
- een pseudonym-token in welke vorm ook: hoofd- of kleine letters, met of
  zonder haken, type en id aan elkaar of met spaties in de id
  (`[person:deadbeef]`, `PERSON3fa9c2d1`, `PERSON: 3fa9 c2d1`), en een kale id
  van acht hex-tekens met een cijfer erin;
- een plaatshouder tussen `[]`, `<>` of `{}` (`[Persoon]`, `[PERSOON-1]`,
  `<naam>`);
- alles wat een adres kan zijn: `@`, `://`, `mailto:` en elk `woord.tld`.

Afwijzen is niet repareren: het onderwerp houdt wat het had en de telling zegt
`rejected`. Strenger dan strikt nodig, met opzet: een afgewezen label kost
alleen dat de termen blijven staan.

**De kwaliteit is niet getest.** Waar dit gebouwd is draait geen model; de
tests bewijzen de leidingen en de controle. Of zes woorden van `llama3.2:3b`
deugen, blijkt bij de generale repetitie (vraag M7). Een slecht label krijgt
een naam van een mens, en die wint.

### Een heel dossier: het commando

    python -m wordsworth.onderwerpen_labelen --dossier gooise-meren-woo-2022

`--dossier` is de **naam**, zoals de console hem toont (niet de uuid die
`samenvatten` vraagt). Alleen onderwerpen zonder label; `--opnieuw` doet ze
allemaal. Eén regel uitvoer:

    seen=17 labelled=15 rejected=1 no_summaries=1 skipped=0 failed=0 model=llama3.2:3b duur=2040.3s

`skipped` had al een label, `failed` is een modelaanroep die faalde. De
exitcode is niet nul bij een mislukte aanroep, een onbereikbare zoekindex of
een onbekend dossier. Een afgewezen label of een onderwerp zonder
samenvattingen is geen fout: dat staat in de regel.

**Kosten:** ongeveer twee minuten per onderwerp op de hardware van het
cluster; de zeventien onderwerpen van Gooise Meren zijn ruim een half uur. Elk
label wordt meteen opgeslagen, dus een afgebroken run verliest alleen het
onderwerp waar hij mee bezig was, en de volgende run slaat de rest over.

### Eén onderwerp: de route en de knop

`POST /topics/{topic_id}/label` labelt één onderwerp en geeft het label met
model en datum terug, of `labelled: false` met `reason` (`rejected` of
`no_summaries`). Achter de corpus-leespoort, dezelfde als de samenvattingen;
404 voor een onbekend onderwerp; 409 `er loopt al een label-opdracht` als er
al een label geschreven wordt; 409 `onderwerp is opnieuw berekend` als het
onderwerp tijdens de aanroep verdween; 503 met `language model ...` of
`search index ...` als het model of de index onbereikbaar is. De aanroep duurt
ongeveer twee minuten, dus deze route is voor aanroepers in het cluster. Een
route die een heel dossier labelt bestaat niet, met opzet.

**De knop op de onderwerpenpagina wacht niet.** Een browser bereikt de
console via Cloudflare, dat een verzoek na 100 seconden afkapt, en
oauth2-proxy, standaard na 30 seconden. Een knop die twee minuten wacht krijgt
een foutpagina voor werk dat daarna wél lukt. Dus komt de pagina meteen terug
met "bezig, ververs over ongeveer 2 minuten", en schrijft de server het label in
een achtergrondtaak van dat verzoek. Er loopt er één tegelijk; een tweede klik
zegt "er loopt al een label-opdracht" en start niets. De route en de knop delen
dat ene slot. **Het slot geldt per proces**: twee pods of twee workers kunnen
elk een label tegelijk schrijven. Het commando gebruikt het slot niet; het
draait als een eigen proces. Geen wachtrij en geen
worker: herstart de pod midden in een aanroep, dan is het label er niet en kan
de knop opnieuw.

**Waar de uitkomst van een klik staat:** in het log van de API-pod (stderr),
één JSON-regel op de pipeline-logger `wordsworth.pipeline`, dezelfde die de
statusovergangen schrijft en die `serve.build_app` aanzet:

    {"error": null, "event": "topic_label", "level": "info", "outcome": "labelled", "topic_id": "<uuid>"}

`outcome` is `labelled`, `rejected`, `no_summaries` of `failed`; bij `failed`
staat in `error` alleen de klasse van de fout (`GenerationError`,
`SearchUnavailable`, `TopicRecomputed`, ...). Nooit de tekst van een label:
wat afgewezen werd, kan een token bevatten, en een databasefout draagt het
label als parameter mee.

### Als het model of de index weg is

- **Model weg:** geen onderwerp verliest zijn naam. Het commando telt
  `failed` en eindigt niet-nul; de route geeft 503; de knop logt `failed`, en
  na verversen zegt de pagina nog steeds "label ontbreekt".
- **Index weg:** het lidmaatschap staat alleen in de index, dus er wordt niets
  gelabeld en er verandert niets. Het commando zegt het en eindigt niet-nul; de
  route geeft 503.
- Een **berekening** van onderwerpen roept het model nooit aan en faalt er
  nooit op.

**Herberekenen gooit de labels weg**: het vervangt de onderwerpen, en een
label hoort bij een groep die dan niet meer bestaat. Gebeurt dat terwijl het
model schrijft, dan wordt het label niet opgeslagen: het commando telt
`failed` en gaat door met het volgende onderwerp, de route geeft 409 en de knop
logt `failed`. De pagina zegt daarna
welke labels ontbreken en noemt het commando.

## Meten

```sh
python -m wordsworth.eval.topics_run --dossier <uuid> \
  --gold eval/gold.jsonl --queries eval/queries.tsv --qrels eval/qrels.txt
```

Twee getallen, want het zijn twee vragen:

1. **de indeling** — adjusted rand index en purity tegen het bekende onderwerp
   uit `gold.jsonl`. Naast elkaar, want purity wordt te makkelijk hoog (één
   groep per document geeft 1.0) en de ARI leest te makkelijk laag zonder iets
   ernaast;
2. **het zoeken** — dezelfde queries met en zonder onderwerp-scope, met de
   bestaande metrieken.

Het onderwerp voor (2) wordt gekozen zoals een mens het zou kiezen die het
júiste onderwerp aanklikt. Dat meet het plafond en niet het gemiddelde.

**De verwachting stond vóór de meting opgeschreven:** (2) beweegt niet of
nauwelijks — een scope die de juiste documenten bevat, haalt bovenaan dezelfde
documenten naar boven. Gaat (2) omláág, dan is de scope te smal en klopt de
indeling niet. De winst zit in (1), en in iets dat deze getallen niet vangen:
dat een mens ziet waar een dossier over gaat voordat hij zijn eerste zoekterm
verzint.

## Wat dit niet doet

- Geen onderwerpen over dossiergrenzen heen.
- Geen taalmodel in de berekende naam. Een label van het model staat ernaast,
  met zijn herkomst (zie *Labels van het taalmodel*); een berekening roept het
  model nooit aan.
- Geen invloed op de score.
- Geen automatische herberekening. Een document dat opnieuw door de straat
  gaat (`reanonymize`, dus ook `/reprocess`) houdt het onderwerp dat het had —
  berekend over de tekst van vóór die stap. Daarom staat bij elk onderwerp
  wannéér het berekend is: dat is het enige signaal dat een lid er sindsdien
  doorheen is gegaan, tot een nieuwe berekening de indeling vervangt.
