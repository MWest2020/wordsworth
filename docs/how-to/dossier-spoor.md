---
status: current
last_reviewed: 2026-09-22
---

# Wie een document verplaatste, en waarheen

Een dossier bepaalt wat een gescopete zoekopdracht teruggeeft. Een document
verplaatsen verandert dus wat iemand wél en niet ziet — en tot 2026-09-22 bleef
daar niets van over. De securityreview greptte op `audit` over `dossiers.py`,
`dossier_tools.py` en `backfill_dossier.py` en vond **nul** treffers. Je zag
achteraf de uitkomst en niet de handeling.

## Twee soorten feit, twee plekken

| wat | waar | waarom |
|---|---|---|
| lidmaatschap erbij of eraf | de **hashketen van dat document** | het gaat over één document |
| dossier hernoemd | de **sleutel-levensloopstroom** | het verplaatst geen document |

Die scheiding is de hele beslissing. Een hernoeming raakt duizend documenten
zonder er één te verplaatsen; duizend identieke records zouden de keten
volschrijven met kopieën van hetzelfde feit, en één record zonder document past
niet in die tabel. Daarom staat hij waar grants, sleutelrotaties en
rolwijzigingen al staan — dezelfde redenering als in `roles.py`.

## Wat een lidmaatschapsrecord is

Een **gebeurtenis**, geen toestandsovergang: `from == to`, net als
`deanonymize`. Een document dat in een andere zaak belandt, staat in precies
dezelfde staat als daarvoor. Een overgang claimen zou `current_state` laten
liegen.

```
step     : dossier_added | dossier_removed
payload  : dossier, dossier_id, actor [, reason] [, batch]
```

## De reden is verplicht bij weghalen, niet bij toevoegen

Dat is geen slordigheid maar de kern:

- **toevoegen** is terug te zien in het resultaat — het document *staat* er;
- **weghalen** laat niets achter. De enige herleiding is wat iemand op dat
  moment opschreef, en een maand later reconstrueert niemand dat.

`remove()` zonder reden is daarom een `DossierError`, geen waarschuwing.

## Wie het deed

`actor` heeft **geen default**. Een default maakt het anonieme geval het
makkelijkste geval, en dan staat er over een jaar "iemand heeft dit verplaatst".
Aankomen via ingest telt ook als handeling: die records dragen `actor: ingest` —
niemand verplaatste dat document, het arriveerde.

## Eén handeling, honderden records

Een terugvulling die 791 documenten toewijst is eerlijk als 791 records: elk
document kreeg echt een lidmaatschap. Zonder iets dat ze bindt is een dag
geschiedenis alleen niet te lezen — het oogt als honderden losse beslissingen.

Daarom draagt elk record van zo'n run hetzelfde `batch`-kenmerk. Een lezer kan
ze samenvouwen; het spoor blijft per document kloppen.

## Terugzoeken

```sql
-- alles wat er met dit document in dossiers gebeurde
SELECT ts, step, payload FROM audit_records
WHERE document_id = '…' AND step LIKE 'dossier_%' ORDER BY seq;

-- één handeling, alle documenten die hij raakte
SELECT document_id, payload->>'dossier' FROM audit_records
WHERE payload->>'batch' = '…';
```

Hernoemingen staan niet in deze tabel maar in de sleutel-levensloopstroom, als
`dossier_renamed`, met `old`, `new` en **hoeveel documenten** het dossier op dat
moment hield — het getal waarvoor dat record bestaat.
