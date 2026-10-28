# Tasks

## 1. Detection
- [ ] Detect `<first name> <particle> <last name>` as one `PERSON` span, for the
      particles `van`, `de`, `ter`, `ten` and `van der`. Proved by: a test with
      synthetic names, one example per particle, asserting one `PERSON`
      detection covering the whole name and no readable part of it left.
- [ ] Ordinary text is not swallowed. Proved by: a test that a sentence with
      lowercase `de`/`van` between ordinary words yields no `PERSON`.

## 2. The affected document
- [ ] Re-anonymise document `1c87f856`. Proved by: a de-identify audit record
      for it under the new code.
- [ ] Confirm that no untokenised name of that shape remains. Proved by: a
      count-only check over the document's anonymised text (first name,
      particle, last name pattern) that reports a count of 0 and prints no
      value.

## 3. Docs (must change with the code)
- [ ] `docs/explanation/pilot-report-gooise-meren-2022.md`: update the finding
      in sections 4 and 5 with the result of the re-check, as a count. Proved
      by: the file states the count and the date.
- [ ] `docs/reference/evaluation.md`: state that names with a Dutch particle are
      detected as one `PERSON` and how the count-only check is run. Proved by:
      the section exists and contains the command.
- [ ] `openspec validate detect-dutch-particle-names --strict` passes.
