# Design

## Decided

- **Separate change, after the rule.** Re-anonymising is an operation on the
  corpus; the rule is a detection change. The breaker stopped
  `detect-dutch-particle-names` after three builds without a merge, so the
  operation is split off.
- **Reuse reprocess.** `wordsworth/reprocess.py` already writes the failure
  trace, continues on failure and is shared by the endpoint and the Job. A second
  loop would drop that trace, as the 2026-09-20 Job did.
- **Count-only check.** `reprocess_counts.compare(before_text, after_text) ->
  dict` is a pure function: per type, the number of distinct pseudonyms in the
  text before, in the text after, added (in after and not in before) and
  removed (in before and not in after). `reprocess.one` reads the stored
  pseudonymised text before it calls `reanonymize` and again after it
  returned, and logs one structured line with the document id and those
  numbers. Never a value, never a token, never the text around it, never an
  offset. This follows the existing requirement that no measurement logs a
  value.
- **Counts are of distinct pseudonyms, not of occurrences.** One person named
  five times is one. That is what the text carries and what the console shows
  per document. The docs say it, so a reader does not take "PERSON 12" for
  twelve mentions.
- **Added and removed, not only before and after.** A name with a particle
  whose first name was already a token becomes one new token for the whole
  name: before 4, after 4. Equal totals would hide exactly the case this
  change is for; `added 1, removed 1` shows it.
- **Selection by explicit ids.** `only_outdated` compares `lists_hash`, and
  the gazetteer is outside it by requirement. The operator lists the dossier's
  document ids and passes them as `document_ids`. `reprocess.py` is 188 lines
  and gets the one logging call only.
- **A document that is skipped or fails logs no counts.** Its existing outcome
  (`skipped`, `retryable`, `failed`, with the `reprocess_failed` record) says
  what happened.

## What the check does not prove

- That no name is left. It counts what was tokenised, and a name the rule does
  not recognise is not counted before or after. Whether `1c87f856` is fixed is
  read from the document, and depends on the gazetteer (question M6).
- Anything about a document the run did not include.

## Rejected

- **A check that shows the old and new text side by side.** It would print the
  very name the rule is about.
- **Folding this into `detect-dutch-particle-names`.** That is what stalled it.
- **Counting from the pseudonym registry.** It never shrinks, so "after" could
  never be lower than "before".
- **Counting from the `detections` payload of the audit trail.** It was never
  checked against stored records, and it holds the earlier run's view, not what
  the text holds now.
- **Widening `lists_hash` to the gazetteer.** It contradicts a requirement of
  `particle-names-rule` and would make every gazetteer edit mark the whole
  corpus outdated.
- **A new command for the run.** The reprocess path takes ids already.

## The run (operator, not part of the build)

1. List the document ids of the dossier.
2. Reprocess them with `document_ids`, as a Job.
3. Read the count lines; open `1c87f856` and check it by eye.
4. Update the pilot report with the outcome, in its own PR.
