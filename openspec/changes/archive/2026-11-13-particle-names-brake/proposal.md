# particle-names-brake (step 2 of 4)

## Why

Step 1 (`particle-names-rule`) ships the rule with a gazetteer of first names.
A gazetteer entry that is also an ordinary word would turn ordinary text into a
`PERSON` and hide it. This step adds the brake that catches such an entry before
roll-out, split from `detect-dutch-particle-names` (#285). Build after step 1
has merged.

## What changes

- `tests/test_particle_names_veiligheid.py`: every shipped entry is run over
  the generated evaluation corpus (with an occurrence check per entry), plus a
  coverage guard that every particle has a `PERSON` sentence in the fixture.
- `tests/test_particle_names_zinnen.py`: every shipped entry is run over a
  fixture of Dutch sentences, `tests/fixtures/gewone_zinnen_nl.txt`, where
  each sentence states its own expectation, plus the negative controls. Two
  files keep each under 200 lines.
- The fixture has three columns: `PERSON<TAB>sentence<TAB>full name` or
  `GEEN<TAB>sentence`. The third column of a `PERSON` line is the expected full
  name, so the test does not re-derive it with a particle scan that mirrors the
  rule.
- A brake hit fails the test with a message naming the entry. The test never
  edits `src/wordsworth/data/voornamen.json`; removing an entry is a separate,
  human act. The accepted misses `Ton` and `Bart` stay as the applied
  requirement in step 1 fixes them.
- `docs/how-to/detection-lists.md`: one paragraph on the brake.

## Impact

- Specs: `anonymization` (ADDED, one requirement).
- Tests: `tests/test_particle_names_veiligheid.py`,
  `tests/test_particle_names_zinnen.py`, `tests/fixtures/gewone_zinnen_nl.txt` (new).
- Data: none.
- Docs: `docs/how-to/detection-lists.md`.

## Depends on

`particle-names-rule` (merged 2026-11-03).

## Next

`person-aggregate-dedupe`
