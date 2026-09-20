# Tasks

**Gemeten op 2026-09-20 en daarmee grotendeels achterhaald.** Zie het naschrift
in `proposal.md` en `docs/explanation/meting-restwaarden-03.md`. Wat hieronder
nog staat is wat de meting overliet.

## 0. Eerst beslissen
- [ ] Het straatadres via een `deny.json`-patroon (bestaand mechanisme), of in
      de detector zelf? **Nog open, en nog steeds gerechtvaardigd.**
- [x] De invariant "een gepseudonimiseerde waarde staat nergens anders meer
      letterlijk in het document" — **NIET bouwen.** Gemeten: de acht waarden
      die "overleven" zijn gewone woorden (`locatie`, `bewoners`, `week 23`)
      die ten onrechte als PII zijn gezien. Afdwingen zou documenten weigeren of
      de tekst mangelen.

## 1. Meten vóór het repareren
- [x] Geteld op 60 documenten uit het echte corpus: 7 documenten, 8 waarden,
      allemaal gewone woorden.
- [x] Ontsleuteld wat er in het uitgangsdocument stond: `Teaz` en `EAZ`, niet
      "eazwind". Het beschreven geval bestaat niet.
- [x] `docs/explanation/meting-restwaarden-03.md`.
- [ ] Op het evalcorpus is dit nog niet gemeten. Daar is de waarheid bekend, dus
      daar is ook de over-detectie te kwantificeren.

## 2. Het straatadres
- [ ] `deny.json`-patroon op straatachtervoegsels + huisnummer.
- [ ] Test dat `Artikel 5` en `bijlage 3` er niet in lopen.

## 3. De restwaarden — VERVALLEN
Zie het naschrift. Wat hiervoor in de plaats komt is een eigen change over
over-detectie: 39% van de entiteit-tokens heeft een waarde die met een kleine
letter begint, met `gemeente`, `college`, `perceel` en `naam` ertussen.
`allow.json` bestaat daar precies voor en staat in productie nog niet eens aan.

## 4. Daarna pas
- [ ] Het bestaande corpus herverwerken is een APARTE beslissing met een eigen
      prijs. Pas nemen als bekend is hoe groot het gat is.
