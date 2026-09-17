# Change: dossier-scope

## Why

Zoeken gaat over álles wat in de index staat. Dat is niet wat iemand doet. Je
hebt één dossier laten verwerken — een Woo-verzoek, een zaak, een aanlevering —
en je wilt daarin zoeken. Wie het hele corpus doorzoekt, krijgt treffers uit
zaken waar hij niets mee te maken heeft, en moet zelf uitzoeken wat erbij hoort.

Het is bovendien de verkeerde standaard. "Alles" als vanzelf betekent dat een
scope vergeten hetzelfde is als geen scope hebben, en dat is precies de fout die
je niet wilt kunnen maken in een systeem dat over persoonsgegevens gaat.

Wat ontbreekt is geen filter maar een **begrip**. Documenten horen nergens bij.
`documents` heeft geen groep, `ingest_corpus` verwerkt een map en laat niets na
waaruit blijkt dat die documenten bij elkaar horen, en `DatasetRun` is de
CSV-kant en wordt niet opgeslagen.

## Wat deze change WEL doet

- **Een dossier is een entiteit.** Een naam, een moment van aanmaken, en een
  verzameling documenten. Meer niet — alles wat er verder aan zou kunnen hangen
  is een eigen beslissing.
- **Lidmaatschap is veel-op-veel.** Content-adressering betekent dat dezelfde
  bytes één document zijn. Levert iemand hetzelfde PDF in twee dossiers aan, dan
  is dat één document dat in twee dossiers zit — niet twee documenten en ook
  niet een dossier dat het andere overschrijft.
- **Ingest noemt een dossier.** `/ingest` en `wordsworth-ingest` krijgen er een
  mee; zonder is het een fout, geen stille standaard.
- **Zoeken vraagt om een scope.** "Over alle dossiers" blijft mogelijk maar wordt
  een expliciete keuze. Een vergeten scope mag nooit hetzelfde betekenen als
  "alles".
- **De index kan erop filteren.** Het dossier gaat mee bij het indexeren en de
  zoekaanroep neemt het als filter. Dat raakt de driver-seam
  (`SearchIndex.index` en `.search`), dus beide implementaties bewegen mee.
- **Het bestaande corpus krijgt een dossier.** De 791 documenten die er staan
  zijn als één corpus ingeladen; die krijgen één dossier met die herkomst in de
  naam. Zonder dat zou een gescopete zoekopdracht het hele bestaande corpus
  onvindbaar maken, en dat is geen migratie maar een verlies.

## Wat deze change NIET doet

- **Geen grants op dossierniveau.** Een grant is nu per document of globaal, en
  een dossier is de natuurlijke derde scope — maar dat verandert `authorize()`,
  en de autorisatiekern verander je in een change die daarover gaat en niet in
  een change over zoeken. Dat hoort bij de rollen (#80).
- **Geen onderwerpen, geen andere rangschikking.** Alleen de scope verandert;
  wat er binnen die scope gebeurt blijft BM25 en hybride zoals het was. Dat is
  #79 en het leunt hierop.
- **Geen toegangscontrole per dossier.** Wie de API mag bevragen, mag elk
  dossier bevragen. Dat is vandaag ook zo voor documenten; het wordt niet erger
  en het wordt hier ook niet beter. Zie #80.
- **Geen verplaatsen of verwijderen van dossiers.** Toevoegen en lezen. Wat een
  dossier opheffen betekent voor de documenten erin is een eigen vraag.

## Open vragen die deze change moet beantwoorden

1. Krijgt een dossier een door mensen gekozen naam, of een gegenereerde? Een
   naam die een mens kiest is bruikbaar en niet uniek; een gegenereerde is uniek
   en onbruikbaar. Waarschijnlijk allebei: een id en een naam.
2. Wat gebeurt er bij ingest van bytes die al in een ánder dossier zitten? Het
   document bestaat al. Wordt het lid van het tweede dossier, of is dat een
   fout? Dit is de vraag waar het veel-op-veel-model op staat of valt.
3. Wat betekent "alle dossiers" voor iemand die straks maar bij één dossier
   mag? Nu is dat niemand, maar het antwoord bepaalt of #80 erop kan bouwen.

## Impact

- `models.py` (dossier + lidmaatschap), `db.py` (migratie),
  `pipeline.py` (ingest), `api.py` (`/ingest`, `/search`, `/hybrid`),
  `search_index.py` + beide drivers, `console.py`, een terugvul-commando voor
  het bestaande corpus, `openspec/specs/dossiers`.
