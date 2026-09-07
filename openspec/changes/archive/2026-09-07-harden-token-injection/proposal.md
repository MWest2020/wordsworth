# Change: harden-token-injection

## Why

CRITICAL uit de security-review van 2026-09-06.

`mapping_store.get(pseudonym)` zoekt **globaal**, niet per document. Dat is
bewust: dezelfde waarde hoort overal hetzelfde token te krijgen, anders werkt
zoeken over het corpus niet. Maar `_reveal` vervangt élk token dat in de tekst
staat — en de tekst is deels door de aanvrager aangeleverd.

Aanvalspad zoals de review het beschreef:

1. tokens oogsten uit een document dat je mag inzien (`/documents/{id}/anonymized`);
2. die tokens letterlijk in een eigen PDF zetten en die ingesten;
3. een grant vragen die netjes gescoped is op **je eigen** document;
4. `POST /documents/{eigen-id}/reveal` → `authorize()` keurt terecht goed, en
   `_reveal` levert de klare waarden die bij het ándere document horen.

De documentscope van een grant — precies wat we in `harden-global-grant-gate`
hebben aangescherpt — is daarmee betekenisloos.

## What changes

`neutralise_foreign_tokens()` draait als eerste stap van de pseudonimisering:
`[PERSON:5c93c3df]` wordt `(PERSON:5c93c3df)`. De inhoud blijft leesbaar, de vorm
die als sleutel dient is weg, en het aantal komt terug in de counts van de run.

## Waarom neutraliseren en niet weigeren

Een ingest laten klappen op een vierkante haak maakt van elk document een
mogelijke stoorzender, en de repo-cultuur is fail-hard op *PII die doorlekt*, niet
op invoer die er raar uitziet. Neutraliseren haalt het gevaar weg zonder iemand
buiten te sluiten, en de telling maakt het zichtbaar in plaats van stil.

## Wat dit NIET oplost

De mapping-store blijft globaal. Wie langs een andere weg een token in de
opgeslagen tekst van zijn eigen document krijgt, kan het nog steeds onthullen. De
volledige fix is een registratie per document van de pseudonymen die de
anonimisering daar heeft *gemaakt* (niet: die er staan), en `_reveal` daarop
begrenzen. Dat is een schemawijziging met migratie — eigen change, hier bewust
niet in meegenomen. Deze change sluit het pad dat de review daadwerkelijk kon
lopen.

## Impact

- 449 tests groen, vier nieuw waaronder een die de aanval zelf naspeelt.
- Geen schemawijziging, geen migratie, geen gedragsverandering voor tekst zonder
  tokenvormen.
