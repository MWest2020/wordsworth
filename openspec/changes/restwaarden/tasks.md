# Tasks

**Gemeten op 2026-09-20 en daarmee grotendeels achterhaald.** Zie het naschrift
in `proposal.md` en `docs/explanation/meting-restwaarden-03.md`. Wat hieronder
nog staat is wat de meting overliet.

## 0. Eerst beslissen
- [x] Het straatadres via een `deny.json`-patroon (bestaand mechanisme), of in
      de detector zelf? **Via `deny.json`.** Het mechanisme bestaat, draait al in
      productie voor de allow-lijst, en een regel mét reden is na te kijken door
      iemand die geen Python leest. Een detector erbij zou hetzelfde doen met
      meer code en zonder die leesbaarheid.
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
- [x] Op het evalcorpus is dit nog niet gemeten. Daar is de waarheid bekend, dus
      daar is ook de over-detectie te kwantificeren. Gedaan in
      `docs/explanation/meting-overdetectie-05.md` (mét en zónder lijsten over
      500 documenten).

## 2. Het straatadres
- [x] `deny.json`-patroon op straatachtervoegsels + huisnummer. De achtervoegsels
      die óók gewone woorden eindigen (`ring`, `baan`, `pad`, `hof`, `park`)
      staan er bewust NIET bij: "Verandering 3" is geen adres.
- [x] Test dat `Artikel 5` en `bijlage 3` er niet in lopen — plus `Postbus 1234`
      en een straatnaam zonder nummer.
- [ ] **Voor Mark.** Het evalcorpus zaait het woonadres als gewone tekst en niet
      als PII (`generate_ground_truth.py`, `.lit(f"{straat} {nummer}, ")`). Zolang
      dat zo is, telt deze regel daar als precisieverlies en is de winst er niet
      te meten. Dat is een uitspraak over wat PII IS, en die hoort niet uit een
      regex te volgen.

## 3. De restwaarden — VERVALLEN
Zie het naschrift. Wat hiervoor in de plaats komt is een eigen change over
over-detectie: 39% van de entiteit-tokens heeft een waarde die met een kleine
letter begint, met `gemeente`, `college`, `perceel` en `naam` ertussen.
`allow.json` bestaat daar precies voor en staat in productie nog niet eens aan.

## 4. Daarna pas
- [x] Het bestaande corpus herverwerken is een APARTE beslissing met een eigen
      prijs. Mark, 2026-09-21: *"draai die reprocess maar"*. Gedraaid onder
      lijst-hash `64b00c66`: 770 documenten, 15,4 uur, en daarna nul
      achterstallig (uit het spoor gecontroleerd, niet uitgerekend).
      Twee documenten vielen onderweg om op `ObjectStoreError ←
      EndpointConnectionError`: de SeaweedFS-pod herstartte midden in de run.
      Dat is de bedoelde faalweg — hard falen per document in plaats van
      onversleuteld doorlaten, de oorzaakketen in het spoor, en die twee blijven
      "verouderd" tot een herhaling ze oppakt. Dat deed de herhaling ook: precies
      die twee, 399 seconden, nul mislukkingen.
- [x] **Wat de regel opleverde: 3.231 straatadressen in 403 van de 770
      documenten.** Gemeten aan de `list`-laag in het detectie-spoor van die run
      zelf — een deny-regel schrijft zijn eigen toevoeging daar weg, dus dat
      getal is per constructie wat de regel deed, onder één versie.
