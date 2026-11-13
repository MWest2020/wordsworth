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

1. **A count-only check in the reprocess path.** For each re-anonymised
   document, one log line gives, per type, the number of distinct pseudonyms in
   the stored text before and after, and how many were added and removed. No
   value, no token, no text, no offset. The same numbers come back per
   document in the answer of `POST /reprocess` (`ReprocessResponse`), so a Job
   that prints the answer has them in its own log and nobody has to find the
   service's log.
2. **Docs** that describe re-running after a detection change change with it:
   how to select the documents, how to read the line.
3. **The run itself is not part of the build.** Re-anonymising the dossier uses
   the existing reprocess path (`wordsworth/reprocess.py`, `POST /reprocess`
   with `document_ids`). No new reprocess mechanism and no new command.

## Depends on

`particle-names-rule` (merged, archived 2026-11-03), `particle-names-brake`
(built in #381) and `particle-names-measured` (archived 2026-11-06). Nothing
blocks the build.

## Decisions (amended 2026-11-13)

The first version listed these as open questions. They are settled here as
working assumptions; Mark can overrule each.

- **Which documents: an explicit list of ids.** The gazetteer is deliberately
  outside `lists_hash` (requirement "The gazetteer leaves out common words and
  stays out of lists_hash"), so `only_outdated` selects nothing after a
  gazetteer or rule change. The run passes the `document_ids` of the dossier
  (`POST /reprocess` already takes them, `api.py:1256`). Not chosen: widening
  the hash (it would mark the whole corpus outdated on every gazetteer edit)
  and reprocessing every dossier.
- **Where the counts come from: the stored pseudonymised text, before and
  after.** Not the `detections` payload of the earlier audit record (never
  checked against stored records). And not the pseudonym registry as a total,
  which the plan for this amendment named: `pseudonym_registry.register` never
  removes a token (`pseudonym_registry.py:43`), so a registry count can only
  grow and would report tokens the text no longer holds. The text is what the
  reader sees; `pseudonym_registry.tokens_in` reads the tokens off it and
  `label_of` (`pseudonymizer.py:61`) gives the type.
- **Who runs it and when: an operator, after the build, once production is
  reachable.** The build ships the count-only line and the docs. The run over
  the Gooise Meren dossier is an operator step, as a Job and not as one HTTP
  request (it takes hours, see `docs/how-to/detection-lists.md`).
- **The pilot report is updated by that run, not by the build.** The build
  changes no figure in `docs/explanation/pilot-report-gooise-meren-2022.md`.

## Questions for Mark that this change does not settle

- **M6.** The gazetteer holds 12 first names, all from the synthetic corpus;
  the real name in `1c87f856` was never recorded. The run may therefore leave
  that document as it is, and the roadmap item "No untokenised names left"
  (#285) does not close on this build or on the run alone. Default: extend the
  gazetteer through the existing brake with an open list of common Dutch first
  names (licence checked, each entry with its source), and Mark adds the one
  known name himself; then the run. That default costs more than a list: the
  brake (`tests/test_particle_names_veiligheid.py`) fails any shipped entry
  that the generated evaluation corpus never uses as a first name before a
  particle and a last name, so every added name must also be seeded in
  `src/wordsworth/eval/synthetic.py`. Extending the generator is part of the
  work, and a list of a few hundred names is a change of its own, not a file
  drop.
- **M5.** The run needs the deployed corpus, which cannot be reached while
  jumpy is offline. Default: the build merges on green CI plus the local
  check; the run waits.

## Impact

- Specs: `anonymization` (ADDED, one requirement).
- Code: a new helper module `reprocess_counts.py` (the pure comparison, the
  read of the stored text, the log line); `reprocess.one` and `reprocess.run`
  call it; one new field on `ReprocessResponse`.
- Docs: `docs/how-to/detection-lists.md` (section "Het bestaande corpus
  bijwerken").
