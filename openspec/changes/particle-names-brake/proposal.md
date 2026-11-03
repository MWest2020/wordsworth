# particle-names-brake (step 2 of 4)

## Why

Step 1 (`particle-names-rule`) ships the rule with a gazetteer of first names.
A gazetteer entry that is also an ordinary word would turn ordinary text into a
`PERSON` and hide it. This step adds the brake that catches such an entry before
roll-out, split from `detect-dutch-particle-names` (#285). Build after step 1
has merged.

## What changes

- `tests/test_particle_names_veiligheid.py`: every shipped entry is run over
  the generated evaluation corpus (with an occurrence check per entry) and over
  a fixture of Dutch sentences, `tests/fixtures/gewone_zinnen_nl.txt`, where
  each sentence states its own expectation.
- If the brake catches an entry, that entry leaves `src/wordsworth/data/voornamen.json`
  in the same change.
- `docs/how-to/detection-lists.md`: one paragraph on the brake.

## Impact

- Specs: `anonymization` (ADDED, one requirement).
- Tests: `tests/test_particle_names_veiligheid.py`, `tests/fixtures/gewone_zinnen_nl.txt` (new).
- Data: `src/wordsworth/data/voornamen.json` only if the brake catches an entry.
- Docs: `docs/how-to/detection-lists.md`.
