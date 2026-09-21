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
- [x] `WORDSWORTH_DETECTION_LISTS` aanzetten in de configmap (na het uitrollen
      van het image dat de lijst bevat). Staat aan: `/app/lists`.

## 2. De rem
- [x] `tests/test_allow_list_veiligheid.py`, inclusief de LOSSE WOORDEN van een
      ingezaaide waarde — mijn eerste versie keek alleen naar de volledige
      waarde en liet `^vries$` passeren.
- [x] De recall-meting mét en zónder lijsten draait pas als de lijst aanstaat.
      Gedraaid over het evalcorpus (500 documenten), detectie één keer per
      document en alleen de lijsten erachter verschillend:
      `docs/explanation/meting-overdetectie-05.md`. Daarvoor kreeg
      `python -m wordsworth.eval.pii_run` een `--lists`; zonder die vlag meet de
      CLI de detectie zónder lijsten, ook waar ze aanstaan.

## 3. Meten
- [x] Vóór: 39% van de entiteit-tokens begint met een kleine letter.
- [x] Effect: 10% van de VOORKOMENS in de tekst verdwijnt (3511 van 34895),
      tegen 1% van de unieke tokens. `docs/explanation/meting-overdetectie-04.md`.
- [x] Ná het aanzetten opnieuw meten, met de recall ernaast. `meting 05`. De
      belangrijkste uitkomst is een waarschuwing: een voor/ná over de reprocess
      heen meet twee veranderingen tegelijk (de lijsten én de code die ertussen
      veranderde) en is daarmee géén uitspraak over de lijst.

## 4. Daarna pas
- [x] Het bestaande corpus herverwerken (`POST /reprocess`) is een APARTE
      beslissing met een eigen prijs. Mark, 2026-09-20: *"draai reprocess maar"*.
      Gedraaid: 569 documenten, twaalf uur, nul mislukkingen; 13.520 detecties
      onderdrukt. 770 van de 779 documenten staan nu onder de nieuwe lijsten.
