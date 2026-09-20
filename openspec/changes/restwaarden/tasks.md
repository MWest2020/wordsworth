# Tasks

Nog niet gebouwd. Eerst de twee beslissingen uit `proposal.md`.

## 0. Eerst beslissen
- [ ] Het straatadres via een `deny.json`-patroon (bestaand mechanisme), of in
      de detector zelf?
- [ ] De invariant "een gepseudonimiseerde waarde staat nergens anders meer
      letterlijk in het document" — aan, met een gemeten ondergrens voor de
      lengte?

## 1. Meten vóór het repareren
- [ ] Tel op het evalcorpus hoeveel ingezaaide waarden de straat overleven.
- [ ] Tel op het echte corpus (770 documenten) hoe vaak een gepseudonimiseerde
      waarde nog letterlijk in zijn eigen document staat. Dat kan vandaag al.
- [ ] Beide getallen met datum in `docs/explanation/`.

## 2. Het straatadres
- [ ] `deny.json`-patroon op straatachtervoegsels + huisnummer.
- [ ] Test dat `Artikel 5` en `bijlage 3` er niet in lopen.

## 3. De restwaarden
- [ ] Na de vervanging: zoek de vervangen waarden terug als deelstring.
- [ ] Ondergrens op lengte, gemeten en niet geraden; overgeslagen waarden worden
      gerapporteerd, niet stil genegeerd.
- [ ] Hoofdletterongevoelig, op woordgrenzen.

## 4. Daarna pas
- [ ] Het bestaande corpus herverwerken is een APARTE beslissing met een eigen
      prijs. Pas nemen als bekend is hoe groot het gat is.
