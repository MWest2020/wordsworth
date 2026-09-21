# Change: overdetectie

## Why

Gemeten op 2026-09-20 over 198 documenten uit het Woo-corpus
(`docs/explanation/meting-restwaarden-03.md`, issue #130): van de 1125 unieke
entiteit-tokens begint **39% met een kleine letter**, en daar zitten `gemeente`,
`college`, `perceel`, `naam` en `bedrijven` tussen.

De tien meest vervangen waarden, met in hoeveel documenten ze voorkomen:

```
111  LOCATION      'Bussum'                  41  LOCATION      'locatie'
 85  LOCATION      'naarden'                 40  LOCATION      'gemeente'
 60  LOCATION      'gemeente Gooise Meren'   24  PERSON        'wij'
 43  ORGANIZATION  'coa'                     22  LOCATION      'woning'
 42  PERSON        'Boudewijnse, Barbara'    20  LOCATION      'perceel'
```

Elke keer dat er "de gemeente" staat, staat er nu `[LOCATION:xxxxxxxx]`. Dat
kost leesbaarheid op élke pagina, blaast het aantal tokens op, en maakt de demo
slechter dan het systeem is. Het verklaart ook waarom sommige extractieve
samenvattingen uit gaten bestaan.

## De eerste bevinding: frequentie kan het criterium niet zijn

Dat lijkt de voor de hand liggende regel — "wat in honderd documenten voorkomt
is geen naam" — en hij is fout. `Bussum` staat in 111 documenten en ís een
plaatsnaam. `Boudewijnse, Barbara` staat in 42 documenten en ís een persoon. Ze
komen vaak voor omdat het corpus over één gemeente gaat, niet omdat ze generiek
zijn.

Wat de twee groepen scheidt is niet hoe vaak ze voorkomen maar **wat ze zijn**:
`locatie`, `woning`, `perceel`, `gemeente`, `college`, `bedrijf`, `omgeving` en
`wij` zijn gewone Nederlandse woorden. Dat is geen statistiek maar taal, en het
oordeel hoort dus van een mens te komen.

**Een woordenlijst erbij halen lost het niet op**, en dat is het waard om op te
schrijven voordat iemand het probeert: `Bos`, `Bakker`, `De Vries` en `Van der
Berg` staan in élk Nederlands woordenboek én op élke achternamenlijst. Een
lexicontoets zou precies de achternamen weggooien die het systeem moet
beschermen.

## Wat ik voorstel

**Een met de hand samengestelde `allow.json`, in de repo, met een reden per
regel.** Het mechanisme bestaat al (`detection_lists.py`,
`docs/how-to/detection-lists.md`) en staat in productie niet aan.

De meting hierboven is de **kandidatengenerator**, niet de beslisser: de vaakst
vervangen waarden met een kleine letter zijn de lijst waar een mens doorheen
loopt. Dat is precies de rolverdeling die `add-detection-feedback` al koos —
feedback komt binnen, een mens maakt er een git-wijziging van.

Een reden per regel, zoals bij `identifying-combinations`: een kale lijst
woorden is een lijst die niemand kan nakijken.

### Waar de lijst woont

**In de repo, mee in het image.** Niet in een ConfigMap. De `lists_hash` staat
in elk de-identificatie-auditrecord, en die hash hoort terug te leiden naar een
commit die iemand heeft bekeken. Een ConfigMap is te wijzigen zonder review, en
dan is de hash een getal zonder herkomst.

### De gevaarlijke kant, en de rem erop

Een allow-lijst haalt bescherming wég. Dat is de enige plek in dit systeem waar
een wijziging stilletjes tot minder pseudonimisering leidt. Vier remmen:

1. **Getypeerd en volledig verankerd.** `^gemeente$` onder `LOCATION` raakt geen
   `PERSON`, en raakt ook niet `gemeente Gooise Meren`. Dat doet
   `detection_lists.py` al zo.
2. **Een reden per regel**, in het bestand zelf.
3. **Elke onderdrukking wordt geteld** in het auditspoor
   (`suppressed_by_list`, bestaat al). Onzichtbaar minder pseudonimiseren kan
   dus niet.
4. **Een harde toets op het evalcorpus.** Daar is bekend wat er aan PII in zit.
   Een regel die een ingezaaide waarde onderdrukt, is per definitie fout, en dat
   is automatisch vast te stellen. Die toets hoort in CI, niet in een runbook.

Die vierde is de reden dat ik dit durf voor te stellen. Zonder het evalcorpus
zou een allow-lijst een kwestie van vertrouwen zijn.

## De vraag die ik niet zelf kan beantwoorden

**Telt een overheidsorgaan als persoonsgegeven?**

`gemeente Gooise Meren` (60 documenten), `college` (19), `coa` (43), `ofgv`
(20), `regiogv` (19) zijn organisaties, geen personen. In een Woo-publicatie
wordt het bestuursorgaan bovendien bij wet genoemd: het stuk gáát over wat de
gemeente besloot.

Ze nu pseudonimiseren kost leesbaarheid zonder iets te beschermen. Maar
`ORGANIZATION` is óók waar een eenmanszaak zich verstopt — "Jansen Advies" is
een organisatie én een persoon.

Mijn neiging: bestuursorganen en publieke instanties op de allow-lijst, per naam
en niet per regel, met de reden erbij. Maar dit is een keuze met een juridische
staart en hij hoort van jou te komen, niet van mij.

## Hoe we weten of het helpt

1. **Het evalcorpus**: de recall op ingezaaide PII mag niet dalen. Dat is een
   getal, geen gevoel, en het hoort in CI.
2. **Het echte corpus**: hoeveel entiteit-tokens blijven er over, en welk deel
   daarvan begint nog met een kleine letter? Vandaag 39%; na de lijst hoort dat
   meetbaar lager te zijn zonder dat (1) beweegt.

## Wat deze change niet doet

- **Geen auto-learning.** De lijst blijft mensenwerk in git.
- **Geen lexicon.** Zie hierboven: dat gooit juist achternamen weg.
- **Geen herverwerking van het bestaande corpus** binnen deze change.
  `POST /reprocess` bestaat; wanneer je hem draait is een aparte beslissing met
  een eigen prijs (770 documenten opnieuw door de straat).
