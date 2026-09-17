# Tasks

## 1. Zoeken
- [x] `/console/search` over het bestaande `search_index`, met voorgestelde
      termen als voorbeelden en niet als belofte.
- [x] Fragment uit de **opgeslagen gepseudonimiseerde tekst**. Een fragment uit
      een brondocument ziet er hetzelfde uit en bewijst het tegenovergestelde.
- [x] Een kapotte index meldt de fout in plaats van een lege lijst. "Niets
      gevonden" en "de index ligt eruit" zien er voor een lezer identiek uit, en
      één ervan betekent dat er niets matchte.
- [x] Zonder index zegt de pagina dat.

## 2. Onthullen
- [x] De grants die voor dit document gelden, inclusief die van iemand anders —
      dát is de demonstratie: het scherm biedt hem aan, de deur weigert hem.
- [x] Schakelaars per PII-type; die zijn geen versiering, `authorize()` snijdt de
      gevraagde types door de grant heen.
- [x] `console.js` roept het bestaande `POST /documents/{id}/reveal` aan met het
      cookie dat je al hebt. Geen regel autorisatiecode, geen sleutel, geen eigen
      spoor. Een weigering wordt getoond.
- [x] De console mag zelf geen grants uitgeven; staat er geen, dan zegt de pagina
      dat en hoe het wel moet.

## 3. Het auditspoor
- [x] Onder de knop, op dezelfde pagina. Een auditspoor waar niemand naar kijkt
      is een belofte, geen controle.
- [x] **Gevraagd en opgelost staan apart.** Het auditveld `types` is wat er
      werkelijk uit de mappingstore kwam; een verzoek kan een type noemen en
      niets opleveren. Eén lijst laat "niets opgelost" er precies zo uitzien als
      "niets gevraagd".

## 4. De uitlijning, en waarom die apart getoetst is
- [x] `wwAlign` is zuiver en zonder DOM, en wordt getoetst met **node op het
      echte bestand** — acht gevallen in `tests/test_console_align.js`, vanuit
      pytest aangeroepen. Een Python-kopie van dezelfde logica toetsen zou de
      kopie toetsen.
- [x] Staat er achter een token geen token meer, dan ligt de staart vast en is
      het einde exact te berekenen. Mijn eerste regel ("anker minstens drie
      tekens") haakte daardoor af op het gewone geval van een token gevolgd door
      een punt.
- [x] Lukt de uitlijning niet sluitend, dan geeft hij `null` en valt het scherm
      terug op de onthulde tekst zonder markering. Liever geen markering dan een
      verkeerde.

## 5. Nagemeten over echte HTTP
Met dezelfde `create_app`, sleutels in het geheugen in plaats van OpenBao:

- grant op mijn eigen naam, alleen BSN aangevinkt → **200**, `revealed_types:
  ["BSN"]`, twee tokens blijven staan.
- grant op naam van `hr` → **403 grant not applicable**, met cookie en al.
- auditspoor op de pagina toont de poging.
- zoekpagina met een onbereikbare index → "De zoekindex gaf een fout:
  ConnectionError", geen lege resultatenlijst.

## Wat deze smoke NIET bewees
De opstelling gebruikte een **verse** `InMemoryKeyProvider`, dus de tokens waren
onder een andere sleutel gemunt en losten niet op: `revealed_types` zei `["BSN"]`
terwijl er niets terugkwam. Dat is een eigenschap van mijn opstelling, niet van
de code — maar het legde wel bloot dat `revealed_types` in het antwoord
"geautoriseerd" betekent en `types` in het auditrecord "werkelijk opgelost".
Twee betekenissen onder bijna dezelfde naam. Buiten de scope van deze change,
maar het hoort opgeschreven.

Reveal in productie draait op OpenBao (reversible mode); dit pad is daar niet
tegen aan gedraaid.
