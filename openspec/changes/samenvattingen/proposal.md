# Change: samenvattingen

## Why

Mark, 2026-09-19: *"een gebruiker kan een vraag stellen en aan de hand daarvan
gerankte documenten. Helemaal mooi als per document ook een korte
samenvatting."*

De ranking staat er. Wat een lezer nu ziet is een bestandsnaam, een score en een
fragment van negentig tekens rond het eerste rakende woord. Bij een vraag is dat
fragment vaak nietszeggend: de vraag deelt zelden woorden met het antwoord, dus
het venster landt willekeurig. Je ziet dát een document hoog staat en niet
waaróm.

## De beslissing waar deze change om draait

Een samenvatting is een **nieuwe tekst, gemaakt door een taalmodel, over tekst
die persoonsgegevens draagt.** Dat is iets anders dan alles wat dit systeem tot
nu toe toont. Een fragment is een citaat — je kunt het terugvinden in de
opgeslagen tekst. Een samenvatting is een bewering.

Drie dingen volgen daaruit, en ze zijn geen van drieën optioneel.

### 1. Over de gepseudonimiseerde tekst, en alleen daarover

Er is geen andere tekst. De samenvatting kan dus tokens bevatten
(`[PERSOON:3fa9c2d1]`), en dat is juist goed: dat is de veilige vorm, dezelfde
die het scherm al toont. **Maar dan hoort de samenvatting ook achter dezelfde
poort te staan als de rest van het corpus** (`WORDSWORTH_CORPUS_READ_LABELS`) en
niet in een export, een URL of een facet te belanden — daar geldt de redenering
van de onderwerpnamen, en daar horen tokens níet.

### 2. Eén keer berekend, niet per vraag

Een samenvatting hangt aan het document, niet aan de vraag. Per zoekopdracht tien
modelaanroepen doen is traag en levert bij dezelfde vraag morgen een andere
tekst. Dus: berekenen op verzoek per dossier — dezelfde vorm als `onderwerpen` —
en opslaan met het moment en het model waarmee het gebeurde.

Dat model erbij is geen administratie. Een samenvatting van `llama3.2:3b` is een
ander ding dan een van een groter model, en over een half jaar wil je kunnen zien
welke je leest.

### 3. Een samenvatting is herkenbaar een bewering

Dit systeem verwerkt persoonsgegevens en de rest ervan is deterministisch: de
pseudonimisering, de ranking, de onderwerpnamen. Een door een model geschreven
zin hoort niet als gelijkwaardig naast een citaat te staan. Het scherm zegt dat
hij gemaakt is, door welk model, en wanneer — en het fragment (het echte citaat)
blijft ernaast staan, niet eronder weg.

## Wat ik voorstel te bouwen

- `document_summaries`: document, tekst, model, moment.
- `POST /dossiers/{id}/summaries` — berekent wat er nog niet is. Zelfde vorm als
  de onderwerpberekening: op verzoek, met een noemer terug (hoeveel gezien,
  hoeveel gemaakt, hoeveel overgeslagen, hoeveel mislukt).
- De zoekpagina toont de samenvatting boven het fragment, met de herkomst erbij;
  staat er geen, dan alleen het fragment en de mededeling dat er nog geen is.
- Een mislukte generatie is **geen samenvatting**. Geen halve tekst, geen
  placeholder die eruitziet als inhoud.

## Wat deze change niet doet

- **Geen samenvatting per vraag.** Dat is `/ask` (RAG) en die bestaat al: één
  antwoord over meerdere bronnen, met een grounding-guard op de citaties. De
  twee door elkaar halen levert een tekst op die noch een documentsamenvatting
  noch een antwoord is.
- **Geen automatische berekening bij ingest.** Zelfde reden als bij onderwerpen:
  het is werk voor een antwoord dat op dat moment niemand leest. Bovendien zou
  de straat dan op het taalmodel gaan wachten.
- **Geen samenvatting in een export of een URL.** Zie 1.

## Hoe we meten of het klopt

Niet met een score — er is geen waarheid over "een goede samenvatting" in dit
corpus, en een getal verzinnen is erger dan er geen hebben. Wat wél toetsbaar is,
en wat de tests dus doen:

- de samenvatting bevat geen klare PII die niet in de gepseudonimiseerde tekst
  stond (ze kan niets anders bevatten, en er hoort een test te staan die dat
  vasthoudt in plaats van het aan te nemen);
- een mislukte generatie levert geen rij op;
- twee keer berekenen doet het werk niet twee keer;
- het model en het moment staan erbij en zijn zichtbaar op het scherm.
