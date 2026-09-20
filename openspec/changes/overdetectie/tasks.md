# Tasks

Gebouwd op 2026-09-20, nadat Mark de openstaande vraag beantwoordde.

## 0. Eerst beslissen
- [x] **Nee.** Mark, 2026-09-20: *"bestuursorganen zijn natuurlijk niet PII -
      het zijn geen (natuurlijke) personen."* Daarom staan ze per NAAM op de
      lijst en niet als regel: zijn eigen redenering (natuurlijke personen) is
      precies waarom een eenmanszaak er níet onder valt.
- [x] In de repo (`lists/`), mee in het image.

## 1. De lijst
- [x] `allow.json` met een reden per regel; het laden weigert een regel zonder.
      62 regels, elk met de reden en het aantal voorkomens erbij.
- [x] Kandidaten uit de meting, de keuze per regel met de hand.
- [ ] `WORDSWORTH_DETECTION_LISTS` aanzetten in de configmap (na het uitrollen
      van het image dat de lijst bevat).

## 2. De rem
- [x] `tests/test_allow_list_veiligheid.py`, inclusief de LOSSE WOORDEN van een
      ingezaaide waarde — mijn eerste versie keek alleen naar de volledige
      waarde en liet `^vries$` passeren.
- [ ] De recall-meting mét en zónder lijsten draait pas als de lijst aanstaat.

## 3. Meten
- [x] Vóór: 39% van de entiteit-tokens begint met een kleine letter.
- [x] Effect: 10% van de VOORKOMENS in de tekst verdwijnt (3511 van 34895),
      tegen 1% van de unieke tokens. `docs/explanation/meting-overdetectie-04.md`.
- [ ] Ná het aanzetten opnieuw meten, met de recall ernaast.

## 4. Daarna pas
- [ ] Het bestaande corpus herverwerken (`POST /reprocess`) is een APARTE
      beslissing met een eigen prijs.
