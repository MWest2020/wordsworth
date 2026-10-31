# Re-anonymise the documents affected by the particle-name rule

## Why

The orchestrator, from the odin coding session, asked to split
`detect-dutch-particle-names` as the breaker says: *"(a) particle names in the
deterministic detector, with tests per particle; (b) re-anonymising the affected
document with a count-only check."* This change is part (b).

The new rule only acts on text anonymised after it ships. A document anonymised
before it, such as `1c87f856` in the Gooise Meren dossier (pilot report, wordsworth
#284), keeps its readable name until it is anonymised again. Without part (b) the
miss is fixed for new documents and stays in the corpus for old ones.

## What changes

1. **Re-anonymise the affected documents** with the existing reprocess path
   (`wordsworth/reprocess.py`, `POST /reprocess`), once
   `detect-dutch-particle-names` has merged. No new reprocess mechanism.
2. **A count-only check.** For each re-anonymised document, only the number of
   detected entities before and after is logged, per type. No value, no text, no
   offset.
3. **Docs** that describe re-running after a detection change change with it.

## Depends on

`detect-dutch-particle-names`. It is not built before that change is merged.

## Open questions

- **Which documents count as affected.** `only_outdated` compares the lists hash
  in the audit trail (`reprocess.outdated`). The particle rule is code plus a
  gazetteer file, and it is not decided whether that moves the hash. If it does
  not, `only_outdated` selects nothing for this change. Not decided: widen the
  hash, select by an explicit id list, or reprocess the whole corpus (hours of
  work, see `docs/how-to/detection-lists.md`).
- **Where the "before" count comes from.** The `detections` payload of the
  earlier `anonymize` audit record may be enough; not checked against stored
  records. Not decided.
- **Who runs it and when.** It needs the deployed corpus, so it is an operator
  step as a Job, not an HTTP request. Not decided whether the build includes a
  command for it.
- **Updating the pilot report** with the result waits for the run.

## Impact

- Specs: `anonymization` (ADDED, one requirement).
- Code: the count-only before/after line in the reprocess path; the selection
  depends on the open question above.
- Docs: `docs/how-to/detection-lists.md` (section "Het bestaande corpus
  bijwerken").
