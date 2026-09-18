# Change: dossier-audit

## Why

Een dossier bepaalt wat een gescopete zoekopdracht teruggeeft. Een document
verplaatsen, een dossier hernoemen of een lidmaatschap weghalen verandert dus wat
iemand wél en niet te zien krijgt — en daar blijft geen enkel spoor van achter.

De securityreview mat het: `grep` op `audit` over `dossiers.py`, `dossier_tools.py`
en `backfill_dossier.py` geeft nul treffers, en de stappen in het spoor zijn
`register, profile, extract, anonymize, index, dataset_pseudonymize, deanonymize`.
Geen dossier.

Dat botst niet met de letter van de invariant — die gaat over de audittabel als
toestandsmachine van een document — maar wel met wat `models.py` zelf belooft
over navertelbaarheid. En het botst met de praktijk: ík heb vandaag 791
documenten verplaatst, negen handmatig in een ander dossier gezet en er één
hernoemd. Wie dat over een maand nakijkt, vindt de uitkomst en niet de
handeling.

## Wat deze change WEL doet

- **Een lidmaatschap dat erbij komt of weggaat is een auditrecord**, op het
  document waar het over gaat. Daarmee valt het onder dezelfde append-only keten
  als de rest.
- **Een hernoeming is een auditrecord**, maar niet op een document: die raakt
  ze allemaal. Waar dat record thuishoort is de open vraag hieronder.
- **Wie en waarom.** De beller staat erin. Een reden is verplicht bij een
  verwijdering en niet bij een toevoeging: iets ergens bij zetten is te
  reconstrueren uit het resultaat, iets weghalen niet.

## Wat deze change NIET doet

- **Geen nieuwe toestand.** Een document verandert niet van staat door in een
  ander dossier te komen; dit zijn gebeurtenissen op een document, zoals
  `deanonymize` dat ook is.
- **Geen spoor van lezen.** Wie een dossier doorzoekt laat niets na. Dat is een
  eigen vraag met eigen kosten en die hoeft nu niet beantwoord.

## Open vragen

1. **Waar hoort een hernoeming?** Het auditrecord hangt aan een document en een
   hernoeming raakt er duizend. Een record per document is eerlijk maar
   onleesbaar; één record zonder document past niet in de tabel. Mogelijk hoort
   dit ergens anders dan in deze keten, en dan is dat het antwoord.
2. **Wat met een terugvulling van 791 documenten?** Dat zijn 791 records in één
   keer. Dat is correct en het maakt het spoor voor die dag onleesbaar. Is dat
   erg genoeg om er iets aan te doen?

## Impact

- `dossiers.py`, `dossier_tools.py`, `backfill_dossier.py`, `api.py`,
  `openspec/specs/dossiers`.
