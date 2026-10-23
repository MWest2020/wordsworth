# A document records where it came from, and one published dossier is the MVP

## Why

Mark, 2026-10-23, to odin: *"kun je met wordsworth een publicatie van de
gemeente gooise meren door de straat halen: ranken en anonimiseren waar nodig."*
And on the purpose: *"wordsworth is for both, really. I think if we need to
create focus, then go for published, but the way I see it: It should be able
to anonymize unpublished docs, rank them for the user and publish."* And:
*"I just don't have large unpublished corpi sadly."*

Odin had a session trace one Gooise Meren publication through wordsworth on
paper. It then consulted architect and reviewer, in #general on 2026-10-23.
They agreed:

- **One publication end to end is a walking skeleton, not an MVP.** A scoped
  search in a dossier with one document returns that document whatever the
  ranker does, so the ranking step cannot fail.
- **The MVP is one published publication as a dossier.** That means 10 to 30
  documents, a handful of questions judged by a person, and residual PII
  checked by a person.
- **The pipeline has one gap for it: provenance.** `/ingest` takes uploads
  only, which is by design (ADR-0001: fetching lives in NiFi above
  wordsworth). But a document does not record where it came from. The source
  URL exists only in an eval script's `herkomst.jsonl`, and the `dossiers`
  spec already forbids bulk-assigning a document without recorded
  provenance.

## What changes

1. **The source travels with the document.**
   - `/ingest` takes an optional `source_url` and `fetched_at`.
   - wordsworth records the sha256 of the original bytes itself, in the
     audit record of the ingest. It already addresses the object by that
     hash. A hash the client supplies would prove nothing, so it is never
     taken from the request.
   - A malformed `source_url` is rejected with a stated reason, never
     dropped.
   - Omitting both fields leaves behaviour exactly as it is: unpublished
     documents have no URL.
2. **A page with no text layer is visible.** The pipeline already marks a
   scan `UNPROCESSABLE_OCR` and tries OCR. This change pins that a document
   whose OCR yields no text ends in a visible error state, never as an empty
   text that is indexed. AGENTS.md calls silent failure the bug.
3. **The pilot is defined, with its gates** (`design.md`). It is run on
   published documents only.

## Non-goals, written down so a green pilot is not misread

- **Anonymisation of unpublished documents: unproven.** Published Woo
  material has already been redacted by the municipality. A pilot on it can
  show residual identifiers and over-redaction, but **not recall**. The
  pilot report does not use the word "recall" for PII.
- **No connector.** Fetching stays in NiFi, or by hand for the pilot.
  `egress-policy` is not decided here.
- **No new detectors.** KENTEKEN, KVK and zaak numbers, and the combination
  check for documents, are findings, not this change.
- **Mark's end picture is the direction, not a requirement:** anonymise
  unpublished documents, rank them, publish. wordsworth produces at most a
  release candidate, and a person releases it. The bridge is a later change:
  unredacted originals of an already-published dossier, under a data
  processing agreement, give a natural gold set, with the municipality's
  redaction as a reference rather than as truth.
