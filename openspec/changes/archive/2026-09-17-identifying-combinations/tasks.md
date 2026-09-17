# Tasks

## 1. De combinatie zelf
- [x] `combinations.py`: `Combination` (types + verplichte reden), `parse`,
      `unbroken`, `findings`. Minder dan twee types is een fout, een lege reden
      ook — een regel zonder motivering is over een jaar niet te beoordelen.
- [x] Tests: te weinig types, lege reden, hoofdletterongevoelig vergelijken.

## 2. Profielvalidatie
- [x] `Profile.combinations`, geparsed in `_check` zodat een declaratie zonder
      reden al bij het laden strandt (400 op de endpoint).
- [x] `Profile.unbroken_combinations()`: elke combinatie waarvan dit profiel
      géén enkel type pseudonimiseert.
- [x] Beide modi tellen hetzelfde. `per_record` geeft de geselecteerde kolommen
      één gedeeld token in plaats van elk een eigen token, maar vervángt ze wel
      (`DatasetRun.transform`, regel 135). Mijn eerste versie nam `{RECORD}` als
      het gepseudonimiseerde type en meldde daardoor combinaties die het profiel
      juist wél brak.
- [x] `DatasetResponse.combinations`, apart van `warnings`: een warning zegt dat
      een níet-geselecteerde kolom op PII lijkt, een combinatie zegt dat een
      verzameling types samen identificeert. Twee uitspraken, twee velden.
- [x] Auditrecord telt `unbroken_combinations` (een getal, nooit een waarde).

## 3. De corpusmeting
- [x] `wordsworth-measure-combinations <profiel-of-lijst.json>`: in hoeveel
      documenten komt elk type van een benoemde combinatie voor.
- [x] Meet op `document_pseudonyms` — de tokens die de pijplijn zelf heeft
      gemunt — niet op een herdraai van de detectoren over de brontekst.
- [x] Types die het corpus nergens draagt worden bij naam genoemd
      (`unobservable_types`). "Komt niet voor" en "kan niet gezien worden" zijn
      verschillende antwoorden, en een kale nul geeft het geruststellende.

## 4. Documentatie en oplevering
- [x] `docs/how-to/dataset-pseudonymisation.md`: het `combinations`-blok.
- [x] `docs/reference/cli.md`: het meetcommando.
- [x] `profiles/example-wi.json` krijgt een gedeclareerde combinatie als
      voorbeeld dat draait.
- [x] Volledige suite tegen echte Postgres.

## Bekende gevolgen
- **`profile_sha256` verandert voor bestaande profielen.** Het veld
  `combinations` zit in `model_dump_json()` en dus in de hash. Oude
  auditrecords houden hun oude hash; dezelfde profielfile opnieuw draaien geeft
  nu een andere. Geen test pinde die waarde, dus niets brak — maar wie een
  auditrecord uit vóór deze change naast een nieuwe run legt, ziet twee hashes
  voor één profiel. Dat is de prijs van het veld en hij is hier opgeschreven in
  plaats van weggepoetst.
- **De meting ziet alleen wat de pijplijn labelt.** `GENDER` en een los
  geboortejaar hebben vandaag geen detector; een combinatie die daarop leunt
  meldt daarom `unobservable_types` in plaats van een getal waar iets uit valt
  af te leiden.
