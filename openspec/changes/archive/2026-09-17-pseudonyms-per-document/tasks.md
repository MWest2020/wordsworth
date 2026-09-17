## 1. De registratie

- [x] 1.1 Tabel `document_pseudonyms` (document_id, pseudonym) met herkomst en
      een index op document_id — reveal loopt er bij elke aanroep langs.
- [x] 1.2 `pseudonym_registry`: `tokens_in`, `register` (idempotent), `registered`.
- [x] 1.3 Registreren na élke anonimisering, op beide schrijfplekken in de
      pijplijn (`process` en `reanonymize`).
- [x] 1.4 Uit de uitvoer lezen mag, omdat `neutralise_foreign_tokens` ervóór
      draait: wat er ná afloop in staat, is daar gemunt.

## 2. De poort

- [x] 2.1 `_reveal` krijgt de geregistreerde verzameling mee; een niet-geregistreerd
      token blijft staan.
- [x] 2.2 Stil weigeren. Melden wélke tokens geweigerd zijn beantwoordt "bestaat
      deze waarde elders in het corpus", en dat antwoord is zelf een orakel.
- [x] 2.3 `deanonymize` haalt de verzameling op per document.

## 3. Gate

- [x] 3.1 Acht tests, waaronder het lek end-to-end: oogst een token uit document A,
      zet het in document B, onthul B — het token blijft staan.
- [x] 3.2 Nagemeten dat die test bijt: met de controle uitgeschakeld lost
      andermans token wél op.
- [x] 3.3 Test dat een backfill-regel zijn herkomst draagt.
- [x] 3.4 Zeven bestaande tests anonimiseerden buiten de pijplijn om en
      registreerden dus niets; die doen nu wat de pijplijn doet.
- [x] 3.5 Volledige suite groen (512).

## 4. Uitrollen

- [x] 4.1 `wordsworth-backfill-pseudonyms`, idempotent, met `--dry-run`.
- [ ] 4.2 **Backfill draaien vóór de nieuwe code live gaat.** Een document zonder
      registratieregels onthult niets. Fail-closed is het juiste gedrag en het
      verkeerde om in productie te ontdekken.
