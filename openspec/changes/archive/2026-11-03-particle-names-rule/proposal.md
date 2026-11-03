# particle-names-rule (step 1 of 4)

## Why

The pilot read of the Gooise Meren dossier found a full name shaped
`<first name> ter <last name>` left readable in a meeting agenda. Detection
splits such a name or misses it. `detect-dutch-particle-names` (#285) set out
the fix but was too big for one build: it hit the breaker on 31 Oct and 1 Nov,
and a split attempt on 3 Nov produced a change without valid spec deltas. It is
now cut into four steps:

1. **particle-names-rule** (this change): the rule, its gazetteer and loader, the
   wiring into the reversible driver, and the tests that pin its shape.
2. `particle-names-brake`: the corpus and fixture brake on the gazetteer.
3. `person-aggregate-dedupe`: the audit aggregate counts a person once.
4. `particle-names-measured`: the rule as an evaluation layer, measured.

Each step leaves main green; 2–4 build on 1 and are built one at a time after it
merges. `reanonymise-particle-name-documents` comes after step 1.

## What changes

- A new module `src/wordsworth/particle_names.py` (≤200 lines): a deterministic
  pattern of gazetteer first name, particle (`van`, `van der`, `van den`, `de`,
  `ter`, `ten`) and capitalised last name, giving ONE `PERSON` span with layer
  `dutch_particle_name`.
- A gazetteer data file inside the package,
  `src/wordsworth/data/voornamen.json`, with `{"naam", "reden"}` entries, and a
  loader that refuses an entry without a reason and fails hard when the file is
  missing.
- `ReversibleAnonymizer.anonymize` adds the rule's detections to the entity
  layer's, before the allow/deny lists apply. The irreversible
  `OpenAnonymiserAnonymizer` is untouched.
- `docs/how-to/detection-lists.md`: the gazetteer section.

## Out of scope (later steps or later changes)

The corpus/fixture brake (step 2), the aggregate dedupe (step 3), the
evaluation layer and measurements (step 4), particles beyond the six,
re-anonymising existing documents (`reanonymise-particle-name-documents`).

## Impact

- Specs: `anonymization` (ADDED, four requirements).
- Code: `src/wordsworth/particle_names.py` (new), `src/wordsworth/data/voornamen.json`
  (new), `src/wordsworth/pseudonymizer.py` (the call in `ReversibleAnonymizer`,
  a few lines only; the file is past 200 lines already and does not grow beyond
  the call).
- Tests: `tests/test_particle_names.py` (new).
- Docs: `docs/how-to/detection-lists.md`.
