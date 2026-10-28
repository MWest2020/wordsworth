# Detect names with a Dutch particle as one PERSON

## Why

The orchestrator, from the odin coding session: *"the pilot report's PII read
(wordsworth #284) found one detection miss in the Gooise Meren dossier: document
1c87f856 has a full name in clear in the anonymised output, shaped '<first name>
ter <last name>' (a Dutch particle), most likely an official in a meeting
agenda. No email addresses, phone numbers, IBANs, BSNs or title-plus-name
survived in the 15-document sample."*

Dutch surnames often carry a particle between first and last name (`van`, `de`,
`ter`, `ten`, `van der`, ...). The pilot report records the miss as a count and
a shape, not as a value (`docs/explanation/pilot-report-gooise-meren-2022.md`,
section 4). A full name left readable in an anonymised document breaks the
promise of the `anonymization` capability, and it is the one leftover the pilot
sample found.

## What changes

1. **Detection**: a first name, a Dutch particle (one or more words: `van`,
   `de`, `ter`, `ten`, `van der`, ...) and a last name are detected as ONE
   `PERSON` span.
2. **A test** with synthetic examples, one per particle.
3. **The affected document is re-anonymised** and checked with a count-only
   check that no untokenised name of that shape remains.

## Open questions

- **Mechanism.** Not decided in the channel: whether the span is widened from
  what the entity layer already finds or found by its own pattern. The apply
  step chooses; it must stay deterministic and must not match ordinary
  capitalised word pairs at large.
- **Which particles are in the list.** The channel named `van`, `de`, `ter`,
  `ten`, `van der` and "...". The full list is not fixed here.
- **Scope of the re-run.** The decision names the affected document
  (`1c87f856`) only. Whether the rest of the corpus is reprocessed
  (`POST /reprocess`, hours of work) is not decided and is not part of this
  change.

## Impact

- Specs: `anonymization` (ADDED, one requirement).
- Code: the PERSON detection step; a new test.
- Docs: `docs/explanation/pilot-report-gooise-meren-2022.md` and
  `docs/reference/evaluation.md`.
