## 1. De binding

- [x] 1.1 `authorize()` krijgt `caller` en `auth_enabled`; bij auth aan moet de
      caller de recipient zijn.
- [x] 1.2 `_is_recipient` vergelijkt exact — geen hoofdletterongevoeligheid, geen
      prefix, geen wildcard. Alleen omringende witruimte wordt genegeerd: dat is
      een transportartefact, geen andere naam.
- [x] 1.3 `/reveal` leest de caller vóór de autorisatie en geeft hem door aan
      beide `authorize`-aanroepen.

## 2. Gate

- [x] 2.1 Zeven tests: recipient mag, een ander niet, geen caller met auth aan is
      een weigering, de vergelijking is exact, en de binding omzeilt de andere
      controles niet (ingetrokken, verlopen, ander document).
- [x] 2.2 End-to-end: een geldige sleutel met andermans grant geeft 403.
- [x] 2.3 Nagemeten dat de tests bijten: met de controle uitgeschakeld vallen er
      drie om.
- [x] 2.4 Volledige suite groen (503).
- [x] 2.5 `openspec validate --strict`.

## 3. Wat dit brak, en waarom dat goed is

- [x] 3.1 `test_reveal_requires_key_and_records_caller` gaf een grant uit aan
      `agent-x` en belde met caller `alice` — en verwachtte 200. Dat was precies
      het lek. De test legt nu de nieuwe regel vast én het geval dat hij dichtzet.

## 4. Uitrollen

- [ ] 4.1 **Deploy-stap, niet vergeten**: met auth aan krijgt een bestaande grant
      waarvan de recipient niet het caller-label is voortaan 403. Controleer de
      actieve grants voordat dit live gaat.
