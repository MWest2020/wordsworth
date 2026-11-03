# Design: particle-names-rule

Decisions carried over from `detect-dutch-particle-names` (its design.md, four
architect rounds), plus the two the last architect FAIL (1 Nov) said were open.

## Settled here

- **Where the gazetteer lives: inside the package.** The file is
  `src/wordsworth/data/voornamen.json`, read with
  `importlib.resources.files("wordsworth").joinpath("data/voornamen.json")`.
  It is NOT read from `settings.detection_lists_dir`: that directory is
  optional (`DetectionLists.load` tolerates its absence, `detection_lists.py`),
  and a gazetteer there would make every deployment without a lists directory
  fail hard on its first document. A file inside the package is always there;
  a missing one is a packaging bug, and that is the hard error the spec asks
  for. `uv_build` ships non-Python files under `src/wordsworth/`; a test reads
  the file through `importlib.resources` so the package path is what is tested.
- **The starting list.** The 12 first names of `eval/synthetic.py` `VOORNAMEN`
  without `Ton` and `Bart` (and `Wil`, which is not in it), each with the reason
  `"synthetisch evaluatiecorpus (eval/synthetic.py)"`. Real-name coverage is
  open and is not claimed: adding a name is a reviewed edit of the file.
- **The rule runs before the lists.** Its detections join the entity layer's
  before `DetectionLists.apply`, so an existing allow rule on `PERSON` can
  suppress a particle name. That is the seam as it is; the docs say so.

## Carried over

- Its own module, not a row in `detectors.DETECTORS` (five code paths read that
  table).
- Anchored on the gazetteer, so `Raad van State` and other institutions never
  match.
- Tests assert on the full-name substring, never on the bare particle, since
  replacement is by value.
- The gazetteer stays out of `lists_hash`; its versioning belongs to
  `reanonymise-particle-name-documents`.
- Reversible driver only; the irreversible driver is pinned as out of scope.

## Why these requirements (moved out of the spec to keep requirements short)

- **One span for the whole name.** What identifies a person is the whole name.
  Detecting first and last name apart leaves the particle readable or yields
  several tokens for one person; the Gooise Meren read found a
  `<first name> ter <last name>` left in clear.
- **Institutions stay readable.** `Raad van State`, `Kamer van Koophandel`,
  `Ministerie van Binnenlandse Zaken`, `Vereniging van Eigenaren` and
  `Hoogheemraadschap van Rijnland` have the same shape; an organisation's name
  is not personal data, and redacting it makes a decision unreadable. The
  gazetteer is what keeps them out: `Raad`, `Kamer` or `Ministerie` is not a
  first name.
- **Not in `DETECTORS`.** That table holds validated, high-precision values and
  is read by five code paths; a name rule there would make the evaluation score
  it as deterministic and classify a column of organisation names as `PERSON`.
