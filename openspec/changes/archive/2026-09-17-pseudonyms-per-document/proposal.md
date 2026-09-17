# Change: pseudonyms-per-document

## Why

De mapping-store is globaal: opzoeken gebeurt op pseudonym, niet per document.
Dat is bewust — dezelfde waarde krijgt overal hetzelfde token, en dat is wat een
pseudonimisering bruikbaar maakt. Maar het betekent ook dat `_reveal` **elk**
token oplost dat het in een tekst tegenkomt, ongeacht welk document het maakte.

`harden-token-injection` sloot het pad dat de review daadwerkelijk kon lopen:
tokens die al in de aangeleverde tekst staan worden onschadelijk gemaakt
(`[PERSON:5c93c3df]` → `(PERSON:5c93c3df)`). Die change zei er zelf bij dat de
volledige fix een registratie per document is, en schoof die door omdat het een
schemawijziging met migratie vergt.

Dat is deze change. De reden om hem nu wel te doen: de guard is één regel
verdediging op één plek. Elke nieuwe weg waarlangs tekst in een document komt —
een importpad, een OCR-herstel, een herindexering die de guard overslaat, een bug
in de guard zelf — opent het gat opnieuw. Een registratie sluit het bij de
*uitgang* in plaats van bij elke ingang.

## What Changes

- **`document_pseudonyms`**: welke pseudonymen bij welk document horen.
  Samengestelde sleutel (document_id, pseudonym), plus de herkomst van de regel.
- **Geschreven na elke anonimisering**, uit de resulterende tekst. Dat mag omdat
  `neutralise_foreign_tokens` er vóór draait: wat er ná afloop aan tokens in
  staat, is daar gemunt. De guard maakt "staat erin" gelijk aan "hier gemunt".
- **`_reveal` gaat door de registratie heen.** Een token dat niet bij dit document
  geregistreerd staat, blijft staan — dezelfde stille weigering als een token
  waarvan het type niet is toegestaan of de sleutel niet oplost.
- **Een backfill voor bestaande documenten**, met `source = "backfilled"` in
  plaats van `"minted"`. Dat onderscheid is niet cosmetisch: een backfill leest
  de opgeslagen tekst en kan dus niet zien of een token daar ooit gemunt is of
  vóór de guard is binnengeslopen. Wie later een incident onderzoekt, hoort dat
  verschil te kunnen zien in plaats van het te moeten aannemen.

## Wat hier NIET in zit

- **De cross-document-reveal** (`/reveal` op document A met een token van B) wordt
  hierdoor gesloten, maar de mapping-store zelf blijft globaal. Dat is opzet:
  één waarde, één token, over documenten heen — anders werkt zoeken niet meer.
- **Grants overdraagbaar maken of anders scopen.** Ongewijzigd.

## Impact

- `models.py` (nieuwe tabel), `db.py` (migratie), `pipeline.py` (registreren),
  `pseudonymizer.py` (`_reveal` gaat door de registratie), een backfill-commando.
- **Fail-closed na de migratie**: een document zonder registratieregels onthult
  niets meer. Daarom hoort de backfill bij de uitrol en niet erna — dat staat als
  taak, niet als voetnoot.
