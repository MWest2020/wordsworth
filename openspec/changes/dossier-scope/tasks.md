# Tasks

Nog niet gebouwd. Dit is het plan dat bij het voorstel hoort; de drie open vragen
in `proposal.md` gaan eerst langs Mark, want het antwoord op vraag 2 bepaalt het
model.

## 1. Het model
- [ ] `Dossier` (id, naam, aangemaakt) en `DossierDocument` (dossier + document,
      samen de sleutel). Veel-op-veel, want dezelfde bytes zijn één document.
- [ ] Additieve migratie in `_COLUMN_MIGRATIONS_SQL`-stijl; nieuwe tabellen via
      `create_all`.
- [ ] Index op dossier, want elke gescopete zoekopdracht loopt erlangs.

## 2. Ingest
- [ ] `/ingest` en `wordsworth-ingest` vragen een dossier. Ontbreekt het, dan
      400 respectievelijk een fout — geen standaard.
- [ ] Bytes die al bestaan worden lid van het genoemde dossier (afhankelijk van
      vraag 2 uit het voorstel).
- [ ] Het lidmaatschap als auditfeit, in dezelfde stijl als het domein bij
      `register`.

## 3. De index-seam
- [ ] `SearchIndex.index(...)` krijgt het dossier mee; `search`/`hybrid_search`
      een scope. Beide implementaties (OpenSearch en de in-memory) bewegen mee,
      anders toetsen de tests iets anders dan er draait.
- [ ] OpenSearch-mapping: een `keyword`-veld, en een filter in de query.
- [ ] Een document in twee dossiers staat één keer in de index met twee
      dossierwaarden — niet twee keer.

## 4. De API en de console
- [ ] `/search` en `/hybrid` vragen een scope; zonder scope 400.
- [ ] `?dossier=alle` (of gelijkwaardig) als expliciete brede keuze.
- [ ] De console: een dossierkiezer boven het zoekveld, en de gekozen scope
      zichtbaar in de resultaten zodat niemand zich vergist in wat hij doorzoekt.

## 5. Het bestaande corpus
- [ ] Een commando dat de 791 bestaande documenten in één dossier zet met hun
      herkomst in de naam. Niet doen alsof ze altijd al een zaak waren.
- [ ] Eerst `--dry-run`, zoals de andere terugvullers.

## 6. Bewijs
- [ ] Een test die faalt als een scope wordt vergeten en de zoekopdracht toch
      antwoordt. Dat is de hele belofte van deze change.
- [ ] Een test dat dezelfde bytes in twee dossiers één document zijn.
- [ ] Live-smoke tegen de echte instantie: een gescopete zoekopdracht die een
      document uit een ánder dossier NIET vindt.

## Waarom dit niet als issue kon
Het verandert wat zoeken betekent. Tot nu toe gold: je vraagt iets en je krijgt
alles wat matcht. Straks geldt: je vraagt iets binnen een afbakening, en zonder
afbakening krijg je niets. Dat is een andere belofte, niet een andere knop.
