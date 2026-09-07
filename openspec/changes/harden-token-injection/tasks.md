## 1. Verdediging

- [x] 1.1 `neutralise_foreign_tokens()` in `pseudonymizer.py`.
- [x] 1.2 Als eerste stap in `Pseudonymizer.anonymize` (dus ook in de reversible
      keten, die daarop leunt).
- [x] 1.3 Aantal in `counts["FOREIGN_TOKEN_NEUTRALISED"]`, alleen bij >0.

## 2. Gate

- [x] 2.1 Test die de aanval naspeelt: token van document A overleeft de ingest
      van document B niet.
- [x] 2.2 Test: `[bijlage 3]` en `[PERSON:xx]` blijven ongemoeid.
- [x] 2.3 Test: telling zichtbaar; geen valse melding bij schone tekst.
- [x] 2.4 Volledige suite groen (449 passed, 11 skipped).
- [x] 2.5 `openspec validate --strict` + CI groen.
