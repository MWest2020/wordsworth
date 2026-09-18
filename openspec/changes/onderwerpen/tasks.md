# Tasks

Nog niet gebouwd. Dit is een voorstel: eerst de drie beslissingen uit
`proposal.md`, dan pas code.

## 0. Eerst beslissen
- [ ] Onderwerp = groep documenten met een afgeleide naam? (alternatief: een
      term, of een door een taalmodel bedachte titel — beide afgeraden, met
      redenen in het voorstel)
- [ ] Op verzoek berekenen, niet bij ingest?
- [ ] Filteren en níet de score raken? Dit is de belofte-vraag van deze change.

## 1. Berekenen
- [ ] Onderwerpen per dossier over de gepseudonimiseerde tekst, met `zeef` voor
      embeddings + cosinus + UPGMA. Niets hiervan opnieuw bouwen.
- [ ] Hoeveel groepen? Een vast getal is een aanname; een afkapwaarde op de
      samenhang is er ook een. Wat het ook wordt: het hoort in het resultaat te
      staan, zodat een lezer ziet waaraan hij kijkt.
- [ ] Opslaan mét moment en documentaantal.

## 2. Namen
- [ ] Naam uit de onderscheidende termen van de groep ten opzichte van de rest
      van het dossier.
- [ ] Tokens eruit. **Test: een groep waarvan de sterkste term een token is,
      levert een naam zonder dat token.** Deze test één keer draaien mét de
      filtering eruit; slaagt hij dan ook, dan bewaakt hij niets.
- [ ] Hernoemen door een mens; de berekende naam blijft opvraagbaar.

## 3. Zoeken
- [ ] Onderwerp als scope naast het dossier, langs dezelfde weg als `_scoped()`
      — in `filter`, niet in `must`.
- [ ] Test dat de onderlinge volgorde niet verschuift. Toets dit tegen de
      querybody die de deur uitgaat, niet tegen `InMemoryIndex`; anders bewijst
      de test het model en niet de belofte.

## 4. Meten
- [ ] Generator: bekend onderwerp per document in `gold.jsonl`.
- [ ] Overeenkomst berekende indeling ↔ bekende indeling (ARI of purity).
- [ ] `wordsworth.eval.run` mét en zónder onderwerp-scope, dezelfde queries.
- [ ] De verwachting uit het voorstel staat er vóór de meting. Wijkt de uitkomst
      af, dan is dat de vondst — niet iets om de verwachting op bij te stellen.

## 5. Zichtbaar maken
- [ ] Console: onderwerpen van een dossier, met het moment en het aantal
      documenten erbij. Een oud overzicht hoort oud te lijken.
- [ ] Doorklikken naar zoeken binnen dat onderwerp.

## Raakvlakken
- #104 (dossierwijziging in het spoor): hernoemen van een onderwerp erft het
  antwoord op diezelfde vraag.
- #80 (rollen): niet gekoppeld. Een onderwerp zegt waar iets over gaat, een rol
  wie wat mag zien.
