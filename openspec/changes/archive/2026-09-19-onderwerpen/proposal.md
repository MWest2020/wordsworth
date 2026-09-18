# Change: onderwerpen

## Why

Na het verwerken van een dossier krijg je nu een platte BM25-lijst en moet je
zelf raden waar het over gaat. Bij 770 documenten uit één Woo-publicatie is dat
geen zoekprobleem maar een leesprobleem: je weet niet wélke vragen het corpus
kan beantwoorden.

`zeef` (MIT, al een afhankelijkheid) doet lokale embeddings, cosinus en
UPGMA-clustering. De les uit dat project staat in CLAUDE.md en is hier het
uitgangspunt, niet iets dat we opnieuw ontdekken: **clustering ≠ ranking,
bereik ≠ relevantie.**

## De drie vragen, en wat ik voorstel

### 1. Wat is een onderwerp?

Een **groep documenten binnen één dossier**, met een naam die is afgeleid van de
termen die die groep onderscheiden van de rest van hetzelfde dossier.

Niet een term op zichzelf: dan is het een zoekopdracht met een andere naam. Niet
een door een taalmodel bedachte titel: dan is de naam een bewering waarvan
niemand de herkomst kan navertellen, en dit systeem verwerkt persoonsgegevens —
een label dat erbij verzonnen is, is een label dat in een besluit terecht kan
komen.

Een berekende naam moet **herkenbaar berekend** zijn (de onderscheidende termen,
in volgorde), en een mens mag hem hernoemen. Die hernoeming hoort bij het
dossier thuis en is dus dezelfde vraag die #104 openhoudt: waar hoort een
naamswijziging in het spoor? Deze change wacht dat antwoord niet af, maar erft
het.

### 2. Wanneer wordt het berekend?

**Op verzoek, per dossier.** Niet bij ingest: één document laat geen onderwerpen
zien, en het hele dossier herberekenen bij elk binnengekomen document is werk
dat kwadratisch groeit voor een antwoord dat niemand op dat moment leest.

Het resultaat wordt opgeslagen mét het moment en het aantal documenten waarover
het is berekend. Een onderwerpenoverzicht dat vier maanden en tweehonderd
documenten oud is, moet zichtbaar oud zijn. Anders leest iemand het als de
huidige stand van het dossier, en dat is precies de fout die dit hoort te
voorkomen.

### 3. Verandert een onderwerp de rangschikking, of filtert het?

**Het filtert. In deze change verandert de rangschikking niet.**

Dat is de hele les van zeef in één zin. Dat twee documenten in hetzelfde cluster
zitten zegt dat ze op elkaar lijken; het zegt niet dat ze allebei relevant zijn
voor de vraag die iemand stelt. Cluster-lidmaatschap in de score verwerken maakt
"lijkt op de buren" tot een vorm van relevantie, en dan verschuift de ranking om
een reden die niemand aan de gebruiker kan uitleggen.

Een onderwerp is dus een **scope**, net als een dossier: het versmalt waar je in
zoekt, en laat de volgorde binnen die versmalling met rust. Precies zoals
`_scoped()` het dossierfilter buiten de score houdt.

Wíl je later dat een onderwerp de ranking stuurt, dan is dat een aparte change
met een eigen meting. Deze change legt de meetopstelling aan waarmee die vraag
beantwoordbaar wordt.

## Wat hier niet mag lekken

De enige tekst die dit systeem heeft, is de gepseudonimiseerde tekst. Onderwerpen
worden dus berekend op tokens als `[PERSOON:3fa9c2d1]`, en een onderscheidende
term kan zo'n token zijn.

Een onderwerpnaam is een **veld dat op een scherm belandt, in een export, in een
URL**. Hij hoort dus nooit een token en nooit een klaarwaarde te bevatten — en
"hij bevat toch geen klare waarde, want de tekst was gepseudonimiseerd" is
precies het soort geruststelling dat dit project al een keer duur betaald heeft.
Er hoort een test onder.

## Hoe we meten of het beter is

Zonder getal is "slimmer zoeken" een gevoel. Twee metingen, en ze meten
verschillende dingen:

1. **Klopt de indeling?** De generator (`scripts/eval/generate_ground_truth.py`)
   krijgt per document een bekend onderwerp mee. Daarmee is de clustering te
   vergelijken met de waarheid (adjusted rand index / purity). Dit meet de
   indeling, niet het zoeken.
2. **Helpt het bij het zoeken?** `wordsworth.eval.run` draait de bestaande
   metrieken (`r_precision`, `recall@10`, `map`, `ndcg@10`) mét en zónder
   onderwerp-scope op dezelfde queries.

**Vooraf opgeschreven, zodat het achteraf geen bewegend doel is:** ik verwacht
dat (2) niet of nauwelijks beweegt. Een scope die de juiste documenten bevat,
haalt bovenaan dezelfde documenten naar boven. De winst zit in (1) en in iets
dat deze twee getallen niet vangen — dat een mens ziet waar een dossier over
gaat voordat hij zijn eerste zoekterm verzint. Als (2) wél omhoog gaat, is dat
meegenomen; als (2) omláág gaat, is de scope te smal en klopt de indeling niet.

## Wat deze change niet doet

- Geen onderwerpen over dossiergrenzen heen. Het dossier is de zoekscope en dat
  blijft zo.
- Geen taalmodel in de naamgeving. Zie hierboven.
- Geen invloed op de score. Zie hierboven.
- Geen automatische herberekening. Op verzoek, met een zichtbare datum.
