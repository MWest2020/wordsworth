# Tasks: hoge-beschikbaarheid

Volgorde is dwingend: elke stap is zinloos zonder de vorige.

## 1. Opslag die kan verhuizen (homelab)
- [ ] 1.1 Een opslagklasse kiezen en inrichten die niet aan een node
  vastzit; SeaweedFS is de eerste kandidaat omdat hij er al draait.
- [ ] 1.2 Aantonen dat een volume verhuist: pod op node A, node A weg,
  pod komt op node B met dezelfde inhoud.
- [ ] 1.3 `wordsworth-corpus` migreren naar die klasse.

## 2. De API overleeft één node
- [ ] 2.1 `replicas: 2` met anti-affinity per node.
- [ ] 2.2 PodDisruptionBudget `minAvailable: 1`.
- [ ] 2.3 Controleren dat gelijktijdig schrijven geen kapotte staat
  oplevert (de API is grotendeels lezen; de schrijfpaden expliciet
  nalopen).

## 3. De afhankelijkheden
- [ ] 3.1a OpenSearch met meer dan één node. Wacht op stap 1.
- [x] 3.1b Vastgelegd dát zoeken tijdelijk wegvalt en wat de console dan
  toont: `docs/how-to/zoeken-valt-weg.md`. Het onderscheid tussen "de index
  is onbereikbaar" en "je vraag is afgewezen" bestond niet — beide gaven de
  klassenaam van een uitzondering — en zit nu in de naad
  (`search_index.SearchUnavailable`), niet in de console. Alleen de leespaden
  worden zachter; ingest faalt hard en houdt het document tegen, want
  `indexed` zonder index is een leugen.
- [ ] 3.2 Ollama: gedeeld volume of een tweede instantie.

## 4. Bewijs
- [ ] 4.1 Een uitschakel-test: één node eruit, console blijft
  antwoorden, en het resultaat staat in de documentatie.
- [ ] 4.2 Pas daarna mag "hoogbeschikbaar" in de documentatie staan.
