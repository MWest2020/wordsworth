# Tasks — harden-grant-document-check

## 1. Weigering

- [x] 1.1 `POST /grants` controleert binnen de bestaande sessie
      `current_state(session, doc_id)` en geeft 404 "unknown document" vóór
      `issue_grant`. Uitgevoerd als `session.get(Document, doc_id)` —
      dat is precies de voorwaarde van de foreign key, en geen omweg via
      de audit-trail.

## 2. Tests

- [x] 2.1 Test: uitgifte met een onbekend maar goed gevormd `document_id`
      geeft 404, en er staat daarna geen grant en geen audit-event.
- [x] 2.2 Test: uitgifte met een bestaand document blijft 201.
- [x] 2.3 Volledige suite groen (451 passed, 11 skipped) +
      `openspec validate --strict`. Drie bestaande PPL-tests gebruikten een
      verzonnen document-id; die maken nu eerst de documentrij aan.

## 3. Deploy

- [x] 3.1 `sha-d708df6` gebouwd, in `MWest2020/homelab` gebumpt (api én
      init-job samen) en door ArgoCD uitgerold. Live nagemeten op de pod:
      een onbestaand `document_id` geeft **404 "unknown document"**, een
      bestaand document nog steeds **201**. De testsleutel is daarna
      weer uit `wordsworth-apikeys` gehaald en de geminte grant
      ingetrokken.
