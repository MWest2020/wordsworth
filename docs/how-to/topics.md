---
status: current
last_reviewed: 2026-09-19
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

Hernoemen:

```sh
curl -XPATCH $API/topics/<topic-uuid> -H 'content-type: application/json' \
  -d '{"name":"Kapvergunningen 2022"}'
```

De berekende naam blijft staan. Een lege naam haalt de gegeven naam weer weg.

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
- Geen taalmodel in de naamgeving.
- Geen invloed op de score.
- Geen automatische herberekening. Een document dat opnieuw door de straat gaat
  valt uit zijn onderwerp — daarom staat bij elk onderwerp wannéér het berekend
  is.
