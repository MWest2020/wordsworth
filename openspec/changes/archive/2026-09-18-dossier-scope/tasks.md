# Tasks

Gebouwd. Vraag 2 is beantwoord (lid worden van het tweede dossier, geen fout) en
dat bepaalde het model.

## 1. Het model
- [x] `Dossier` (id, naam, aangemaakt) en `DossierDocument` (dossier + document,
      samen de sleutel). Veel-op-veel, want dezelfde bytes zijn één document.
- [x] Additieve migratie in `_COLUMN_MIGRATIONS_SQL`-stijl; nieuwe tabellen via
      `create_all`.
- [x] Index op dossier, want elke gescopete zoekopdracht loopt erlangs.

## 2. Ingest
- [x] `/ingest` en `wordsworth-ingest` vragen een dossier. Ontbreekt het, dan
      400 respectievelijk een fout — geen standaard.
- [x] Bytes die al bestaan worden lid van het genoemde dossier (afhankelijk van
      vraag 2 uit het voorstel).
- [x] Het lidmaatschap als auditfeit, in dezelfde stijl als het domein bij
      `register`.

## 3. De index-seam
- [x] `SearchIndex.index(...)` krijgt het dossier mee; `search`/`hybrid_search`
      een scope. Beide implementaties (OpenSearch en de in-memory) bewegen mee,
      anders toetsen de tests iets anders dan er draait.
- [x] OpenSearch-mapping: een `keyword`-veld, en een filter in de query.
- [x] Een document in twee dossiers staat één keer in de index met twee
      dossierwaarden — niet twee keer.

## 4. De API en de console
- [x] `/search` en `/hybrid` vragen een scope; zonder scope 400.
- [x] `?dossier=alle` (of gelijkwaardig) als expliciete brede keuze.
- [x] De console: een dossierkiezer boven het zoekveld, en de gekozen scope
      zichtbaar in de resultaten zodat niemand zich vergist in wat hij doorzoekt.

## 5. Het bestaande corpus
- [x] Een commando dat de 791 bestaande documenten in één dossier zet met hun
      herkomst in de naam. Niet doen alsof ze altijd al een zaak waren.
- [x] Eerst `--dry-run`, zoals de andere terugvullers.

## 6. Bewijs
- [x] Een test die faalt als een scope wordt vergeten en de zoekopdracht toch
      antwoordt. Dat is de hele belofte van deze change.
- [x] Een test dat dezelfde bytes in twee dossiers één document zijn.
- [x] Live-smoke tegen de echte instantie: een gescopete zoekopdracht die een
      document uit een ánder dossier NIET vindt.

## Waarom dit niet als issue kon
Het verandert wat zoeken betekent. Tot nu toe gold: je vraagt iets en je krijgt
alles wat matcht. Straks geldt: je vraagt iets binnen een afbakening, en zonder
afbakening krijg je niets. Dat is een andere belofte, niet een andere knop.

## Wat het bouwen erbij leerde

**De idempotente skip vrat bijna de belofte op.** `_ingest_one` slaat bytes over
die al in de index staan — verstandig, want dat scheelt de hele straat opnieuw.
Maar dezelfde bytes aanleveren in een ánder dossier is precies het geval waarin
er wél iets moet gebeuren, en de skip kwam eerst. De ene handeling die het
verzoek vroeg, zou stil verdwijnen. Nu voegt het skip-pad het lidmaatschap toe,
werkt het de index bij, en meldt het `added_to_dossier`.

**De index moest mee in de terugvuller.** Het dossier zit per document in de
index, dus lidmaatschappen wegschrijven zonder de index bij te werken laat die
791 documenten onvindbaar — en dan doet het migratiecommando niet het enige
waarvoor het bestaat. `wordsworth-backfill-dossier` herindexeert daarom zelf, en
meldt hoeveel documenten geen opgeslagen tekst hadden (die stonden nooit in de
index; daar gaat niets verloren).

**Een gat dat ik niet kon dichten en dus benoemd heb.** Zonder database is er
niets om een dossiernaam tegen op te lossen. Een scope eisen die je niet kunt
geven maakt zoeken onbruikbaar, dus zo'n installatie doorzoekt alles, zoals
eerst. Dat staat nu als voorwaarde in de eis en niet als uitzondering erbuiten.

**Vijf bestaande tests vielen om** omdat ze zonder dossier ingestten. Dat is de
verandering zelf: ze legden de oude belofte vast. Ze geven nu een dossier mee,
wat elke aanroeper voortaan ook moet.

## Nagemeten, live over HTTP

    ingest zonder dossier -> 400  "name a dossier: a document that belongs to
                                   none is invisible to a scoped search"
    zoeken zonder scope   -> 400  "name a dossier, or 'alle' for every dossier"
    dossier=zaak-a        -> 1 treffer
    dossier=zaak-b        -> 1 treffer
    dossier=alle          -> 2 treffers
    dossier=verzonnen     -> 400  "unknown dossier(s): verzonnen"

En het geval waar het model op staat of valt: `a.pdf` opnieuw aangeleverd in
zaak-b gaf `added_to_dossier`, waarna zaak-b twee treffers had en zaak-a nog
steeds een. In de database: **twee documenten, drie lidmaatschappen.**

## Bij het uitrollen
- [ ] `wordsworth-backfill-dossier "corpus-2026-09"` tegen productie, NA de api —
      anders zitten de 791 bestaande documenten even in geen enkel dossier
      terwijl de nieuwe code wel een scope eist.
