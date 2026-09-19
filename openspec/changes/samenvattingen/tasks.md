# Tasks

Nog niet gebouwd. Eerst de beslissing uit `proposal.md`.

## 0. Eerst beslissen
- [ ] Een samenvatting per document, berekend op verzoek per dossier, met model
      en moment erbij? (Het alternatief is per vraag genereren — traag, en
      morgen een andere tekst op dezelfde vraag.)
- [ ] Naast het fragment en niet in plaats daarvan?

## 1. Opslaan
- [ ] `DocumentSummary` (document, tekst, model, moment).
- [ ] Alleen wat ontbreekt berekenen; bestaande met rust laten.

## 2. Maken
- [ ] Over de gepseudonimiseerde tekst, met de bestaande `Generator`-naad.
- [ ] Een mislukking levert geen rij op en wordt geteld.
- [ ] Noemer terug: gezien, gemaakt, overgeslagen, mislukt.

## 3. Tonen
- [ ] Op de zoekpagina boven het fragment, met herkomst.
- [ ] Geen samenvatting? Dat zeggen, niet leeg laten.
- [ ] Achter de corpus-leespoort, net als de opgeslagen tekst.

## 4. Bewijzen
- [ ] Een test dat een mislukte generatie niets achterlaat.
- [ ] Een test dat twee keer berekenen het werk niet twee keer doet.
- [ ] Een test dat de samenvatting achter de leespoort zit.
- [ ] Een test dat het scherm zegt dát het gegenereerd is en door welk model.
