## ADDED Requirements

### Requirement: Samenvatten heeft een eigen commando

Het samenvatten SHALL aan te roepen zijn als commando
(`python -m wordsworth.samenvatten`), met een of meer dossiers of met
"alles wat nog geen samenvatting heeft" als invoer. Het commando SHALL
idempotent zijn: een tweede run maakt geen bestaande samenvatting
opnieuw. Het SHALL in één regel rapporteren hoeveel documenten gezien,
gemaakt, overgeslagen en mislukt zijn, en met een exitcode ongelijk aan
nul eindigen als er iets mislukte. Een cluster-Job SHALL dit commando
aanroepen in plaats van een script mee te dragen in zijn argumenten.

#### Scenario: Tweede run doet het werk niet opnieuw

- **GIVEN** een dossier waarvan alle documenten al een samenvatting
  hebben
- **WHEN** het commando opnieuw draait
- **THEN** wordt de generator niet aangeroepen, meldt de uitvoer dat
  alles is overgeslagen, en is de exitcode 0

#### Scenario: Eén document mislukt

- **GIVEN** een dossier waarvan één document geen tekst heeft en de
  rest wel
- **WHEN** het commando draait
- **THEN** worden de overige samenvattingen gemaakt, noemt de uitvoer
  het mislukte aantal, en is de exitcode ongelijk aan nul
