# Change: console-entry

## Why

De console werkt en is toch onbruikbaar.

Wie `/console` in een browser opent zonder geldige sleutel, krijgt
`{"detail":"invalid or missing API key"}` als kale JSON en verder niets. Geen
link, geen formulier, geen aanwijzing dat `/console/login` bestaat. Dat is geen
slot maar een dichtgemetselde deur, en het is precies wat Mark tegenkwam toen ik
hem de URL gaf.

De fout zit niet in de middleware — die doet wat ze moet doen. De fout is dat ik
een inlogpagina bouwde en nergens iets bouwde dat ernaartoe wijst. Ik heb de
stroom getest vanaf de kant waar ik de sleutel al had, en nooit vanaf de kant
waar iemand nieuw binnenkomt.

Er zit een tweede versie van dezelfde fout in het formulier: het aanvaardt elke
tekst als sleutel, zet het cookie, en stuurt je door naar dezelfde JSON-401. Een
tikfout in je sleutel geeft dus geen foutmelding maar dezelfde doodlopende weg.

## Wat deze change WEL doet

- **Een browser komt altijd op een werkende pagina uit.** Op élk pad, niet
  alleen onder `/console`: een geweigerde navigatie gaat naar de inlogpagina, de
  kale hostnaam gaat naar de console, en een onbekend pad ook. Vandaag geven
  `/`, `/console`, `/documents` en `/docs` alle vier dezelfde JSON-401 aan een
  browser — de hele voorkant is een muur.
- **Alleen als de client om HTML vraagt.** Een API-client krijgt onveranderd 401
  JSON: een programma dat een 303 naar een HTML-formulier krijgt, gaat dat
  formulier parsen en meldt een onbegrijpelijke fout.
- **Het formulier toetst de sleutel vóór het het cookie zet.** Een verkeerde
  sleutel geeft het formulier terug met een reden, niet een cookie dat nergens
  toe leidt.
- **Afmelden.** Anders is een verlopen of verkeerd cookie een val waar je alleen
  uitkomt door in de browserinstellingen te graven.

## Wat deze change NIET doet

- **Geen tweede beslispunt.** De middleware blijft bepalen wie erin mag; dit
  verandert alleen hoe een weigering eruitziet voor een mens. Het formulier
  toetst tegen dezelfde sleutelverzameling en beslist alleen of het een cookie
  zet.
- **Geen sessies, geen tokens, geen uitbreiding van het slot.** Dezelfde
  sleutels, dezelfde labels.
- **Geen omleiding zonder bestemming.** Staat de console niet gemonteerd (geen
  api-sleutels), dan blijft alles JSON. Doorsturen naar een pagina die 404 geeft
  is de muur vervangen door een cirkel.

## Impact

- `auth.py` (de weigering), `api.py` (wortelpad + onbekend pad), `console.py`
  (toetsen + afmelden), `templates/`, `openspec/specs/console`.
