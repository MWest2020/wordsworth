# Tasks

Gebouwd op 2026-09-19, nadat de drie beslissingen genomen waren.

## 0. Eerst beslissen
- [x] Onderwerp = groep documenten met een afgeleide naam.
- [x] Op verzoek berekenen, niet bij ingest.
- [x] **Filteren en níet de score raken.** Mark, 2026-09-19: *"filteren is prima,
      ga maar bouwen."*

## 1. Berekenen
- [x] Onderwerpen per dossier over de gepseudonimiseerde tekst. `zeef` levert
      `tokenize`/`cosine`; het clusteren zelf doet scipy (average linkage,
      cosinusafstand) — UPGMA met de hand is precies waar een stille fout in
      gaat zitten. `zeef.pipeline.topics` zelf is niet herbruikt: die hangt aan
      zeefs eigen Document/ProviderBundle/AuditLog en doet twee niveaus.
- [x] Afkapwaarde op de afstand (0.45) plus een ondergrens (3). Allebei staan
      ze in het antwoord én op het scherm.
- [x] Opslaan mét moment en documentaantal.

## 2. Namen
- [x] Naam uit de onderscheidende termen (TF-IDF over het dossier).
- [x] Tokens eruit, vóór het tokeniseren (`pseudonymizer.without_tokens`).
      `test_a_token_never_becomes_part_of_a_name` gecontroleerd mét de filtering
      eruit: dan faalt hij.
- [x] Hernoemen door een mens; de berekende naam blijft opvraagbaar.

## 3. Zoeken
- [x] Onderwerp als scope naast het dossier, in `filter` en niet in `must`.
- [x] De volgorde-test staat er, én de querybody-tests in
      `test_opensearch_scoping.py`. Gecontroleerd met het onderwerp in `must`:
      dan falen er drie.

## 4. Meten
- [x] Generator: bekend onderwerp per document in `gold.jsonl`.
- [x] ARI én purity, naast elkaar — purity alleen wordt te makkelijk hoog.
- [x] `wordsworth.eval.topics_run` doet beide metingen over één corpus.
- [x] De verwachting staat in `topics_run` en in `docs/how-to/topics.md`, met
      de test die eist dat de scope geen juiste documenten wegooit.

## 5. Zichtbaar maken
- [x] Console: `/console/topics`, met moment, aantal en de keuzes.
- [x] Doorklikken naar zoeken binnen dat onderwerp, met een weg terug.

## Raakvlakken
- #104 (dossierwijziging in het spoor): hernoemen van een onderwerp erft het
  antwoord op diezelfde vraag.
- #80 (rollen): niet gekoppeld. Een onderwerp zegt waar iets over gaat, een rol
  wie wat mag zien.
