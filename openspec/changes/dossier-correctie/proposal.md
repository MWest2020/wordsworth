# Change: dossier-correctie

## Why

Ik heb 791 documenten in één dossier gezet met de naam `corpus-2026-09`. Dat is
fout op twee manieren tegelijk, en Mark zag ze allebei meteen:

**De naam zegt wanneer wij iets deden, niet wat het is.** Een datumstempel is
geen dossiernaam. Een dossier heet naar de zaak.

**Het zijn twee corpora, niet één.** De registratiedata laten dat zien:

    2026-08-17   414        2026-09-13   203 (197 met naam)
    2026-08-18    93
    2026-08-19    80
    2026-08-27     1

De augustusset is met de hand geladen en bestaat uit collegevoorstellen,
aanvraagformulieren en vergaderuitnodigingen — de Woo-publicatie van Gooise
Meren uit 2022. De septemberset komt van `open.gelderland.nl`, en de fetcher
schreef daar per document de herkomst van weg: de bron-URL én het **besluit**
waar het bij hoort.

Die besluiten zijn de echte dossiers:

    118  Woo-besluit over aanbesteding pilot Team Vee
     32  Woo-besluit over Ballonfiesta Barneveld
     26  Woo-besluit over Windpark Echteld-Lienden
     11  Aanvullend Woo-besluit over omgevallen boom in Winterswijk
      8  Tweede aanvullend Woo-besluit over sloop energiecentrale Engie
      3  Z26-WO-0032 toepassen grond of baggerspecie Panovenweg Tiel
      2  Woo-besluit over ecologische rapporten Ballonfiesta

Een Woo-verzoek, een besluit en een inventarislijst die bij elkaar horen: dat is
wat een dossier ís.

## De vraag die `dossier-scope` openliet

Die change zei: *"Geen verplaatsen of verwijderen van dossiers. Toevoegen en
lezen. Wat een dossier opheffen betekent voor de documenten erin is een eigen
vraag."* Dit is die vraag, en het antwoord is kort: een lidmaatschap kan weg, en
een document dat daardoor nergens meer bij hoort is geen fout maar wel iets dat
het systeem moet zeggen.

Zonder dat antwoord kan een verkeerd geplaatst document nooit worden rechtgezet,
en dan is de eerste vergissing bij het indelen meteen de laatste — precies mijn
situatie.

## Wat deze change WEL doet

- **Een lidmaatschap kan weg.** De inverse van toevoegen, met dezelfde vorm:
  het weghalen van een lidmaatschap dat er niet is, is geen fout.
- **Een dossier kan een andere naam krijgen.** De identiteit is het id, niet de
  naam; hernoemen verplaatst dus geen enkel document.
- **Een document dat nergens meer bij hoort wordt geteld en gemeld**, niet
  stilzwijgend toegestaan. Het is onvindbaar voor elke gescopete zoekopdracht, en
  dat hoort iemand te weten op het moment dat het gebeurt.
- **Toewijzen uit een herkomstbestand.** Documenten waarvan de herkomst per stuk
  is vastgelegd, komen in het dossier dat die herkomst noemt. Niet raden: een
  document zonder herkomstregel wordt niet toegewezen en wordt geteld.

## Wat deze change NIET doet

- **Geen dossiers verwijderen.** Een leeg dossier is geen probleem; het
  opruimen ervan is een eigen vraag en die hoeft nu niet beantwoord.
- **Geen automatisch indelen op iets anders dan vastgelegde herkomst.** Raden op
  grond van een datum of een tekstpatroon levert een indeling op die niemand kan
  navertellen, en dan is hij erger dan geen.

## Impact

- `dossiers.py` (verwijderen, hernoemen, wezen tellen), twee commando's,
  `openspec/specs/dossiers`.
