# Change: harden-grant-document-check

## Why

Bij het live nameten van `harden-grant-issuer-scope` (2026-09-09, tegen de
draaiende pod) kwam dit boven water: een `document_id` dat keurig gevormd is
maar niet bestaat, levert **500 Internal Server Error** met een
`ForeignKeyViolation` uit SQLAlchemy in de log.

```
POST /grants {"recipient":"…","ppl":1,"document_id":"00000000-0000-0000-0000-000000000000"}
→ 500
insert or update on table "grants" violates foreign key constraint "grants_document_id_fkey"
```

Drie dingen deugen daar niet aan:

1. **Het is een client-fout, geen serverfout.** Elke andere route in deze API
   antwoordt met 404 "unknown document" — `/documents/{id}`,
   `/documents/{id}/anonymized`, `/documents/{id}/reveal`. Alleen deze route
   valt door naar de database.
2. **De stacktrace lekt schema-details** (tabelnaam, constraintnaam, de hele
   INSERT met parameters) in de applicatielog. Niet naar de caller, maar het is
   ruis in precies de log waarin een operator een grant-incident zou naslaan.
3. **Het is de zwaarste route die we hebben.** Een grant is de sleutel tot
   klare PII; dat die als enige onderscheid tussen "mag niet" en "kapot" aan de
   FK-constraint overlaat, past niet bij de rest van de grant-admin.

De constraint zelf doet zijn werk — er ontstaat geen grant. Dit gaat over het
antwoord, niet over de veiligheid.

## What changes

- `POST /grants` controleert binnen dezelfde sessie of het document bestaat
  (`current_state(session, doc_id) is None`), vóór `issue_grant`, en geeft dan
  **404 "unknown document"** — dezelfde tekst en code als de andere routes.
- Geen grant-rij en geen audit-event bij een onbekend document, net als bij de
  bestaande weigering op een ontbrekende documentscope.

## Wat hier NIET in zit

- De 400 op een *ongeldig gevormd* `document_id` blijft ongewijzigd; die was al
  goed en staat al in de spec.
- Geen wijziging aan de FK-constraint of het schema. De database blijft de
  laatste verdedigingslinie; dit zet er alleen een net antwoord voor.

## Impact

- Non-breaking: een aanroep die vandaag 500 krijgt, krijgt straks 404. Niemand
  kan op de 500 hebben gebouwd.
- Eén extra SELECT per uitgifte met documentscope, op de primaire sleutel.
