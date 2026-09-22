# Tasks

Nog niet gebouwd. Vraag 1 bepaalt de vorm en die kan ik niet zelf beantwoorden.

## 1. Lidmaatschappen
- [x] `dossiers.add` en `dossiers.remove` schrijven een auditrecord op het
      document, met de beller en het dossier. `actor` heeft geen default: een
      default maakt het anonieme geval het makkelijkste geval.
- [x] Een verwijdering vraagt een reden; een toevoeging niet. Zonder reden is
      `remove()` een `DossierError`, geen waarschuwing.
- [x] Geen toestandsovergang: `from == to`, zoals `deanonymize`. Vastgepind in
      `tests/test_dossier_spoor.py`.

## 2. De open vraag die dit blokkeerde — BEANTWOORD
- [x] **Waar hoort een hernoeming?** Mark, 2026-09-22: *"memberships on the
      document chain, rename in key-lifecycle"*. Een hernoeming verplaatst geen
      document, dus hij hoort waar grants, sleutelrotaties en rolwijzigingen al
      staan. Het record draagt `old`, `new` en hoeveel documenten het dossier op
      dat moment hield — hoe ver de wijziging reikte, zonder het duizend keer weg
      te schrijven.
- [x] De terugvulling: per document een record (elk kreeg echt een lidmaatschap)
      mét een gedeeld `batch`-kenmerk, zodat één handeling als één handeling
      leesbaar blijft.

## 3. Gebouwd op 2026-09-22
- [x] `dossier_events.py`: de twee huizen, met de redenering erbij.
- [x] `key_audit.py`: `dossier_renamed` in de stroom en in het driver-contract.
- [x] Alle aanroepers noemen een actor — ingest (`actor: ingest`), de
      verplaats-tool, de terugvulling en de API.
- [x] `tests/test_dossier_spoor.py`: negen toetsen, waaronder dat hernoemen
      géén enkele documentketen aanraakt. Eenmaal gecontroleerd met de
      reden-eis eruit.
- [x] `docs/how-to/dossier-spoor.md`.

## 4. Waarom dit een spec vraagt en geen issue
Het verandert wat het auditspoor belooft te bevatten. Tot nu toe stonden er
stappen van de straat in en één toegangsgebeurtenis (`deanonymize`). Hier komt
een categorie bij: handelingen die veranderen wat een ander te zien krijgt
zonder dat er iets aan het document zelf gebeurt.

## De aanleiding
Ik heb vandaag 791 documenten verplaatst, negen met de hand elders gezet en één
dossier hernoemd. Wie dat over een maand nakijkt vindt de uitkomst en niet de
handeling — en de vraag die dan gesteld wordt is precies "wie heeft dit
verplaatst, en wanneer".
