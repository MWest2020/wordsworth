# A template for the pilot report, with two gate slots only Mark fills

## Why

Mark, 2026-10-23, to odin: *"kun je met wordsworth een publicatie van de
gemeente gooise meren door de straat halen: ranken en anonimiseren waar nodig."*
The pilot (one published publication as one dossier,
`pilot-gooise-meren-politieke-avond-2026-09-23`, 12 PDFs) is ingested. What
remains is the report that says what the run showed. `pilot-ingest-manifest`
left it explicitly for this change: "The full report template stays the later
change `pilot-report-template`."

Two things in `docs/reference/evaluation.md` ("The published-dossier pilot")
decide the shape of the report:

- **The gates are a person's judgment, not the pipeline's.** The ranking gate
  needs 5 questions written before any result is seen; the PII gate needs a
  person to read the anonymized text against the source. If the agent writing
  the report can fill those slots, the report certifies itself. Hence two
  empty slots that only Mark fills.
- **No "recall" for PII.** Published material is already redacted by the
  municipality; there is no unredacted original to miss anything against. The
  report may show residual identifiers and over-redaction, nothing about what
  wordsworth would have missed.

The reviewer's line from `pilot-ingest-manifest` applies to the report too: "A
template that can be filled in afterwards proves nothing." The ranking slot
therefore holds the time the questions were committed and the time of the first
search, so the order can be read off the report.

## What changes

A report template for the pilot, and a requirement that says what a pilot
report contains. The template has these parts:

1. **The check**, copied from `check.json`: who (`checked_by`), when
   (`checked_at`), `robots_txt`, `anubis`, `decision`.
2. **The corpus**: number of documents, number of pages, pages without a text
   layer, scans. It states that with no scans the OCR path is barely tested.
3. **The ranking-gate slot**, empty: Mark's 5 questions, each with the document
   he expects; the time the questions were committed; the time of the first
   search; the outcome. The gate is the existing one: the expected document in
   the top 8 for at least 4 of 5, for this pilot run only.
4. **The PII-gate slot**, empty: Mark's read of the anonymized text of every
   document, and any leftover direct identifier of a private person (name,
   address, e-mail, phone, BSN, IBAN).
5. **Findings so far**: the 567-document dossier `gooise-meren-woo-2022` with
   unknown provenance, and that provenance is not recorded when a document is
   delivered again (a duplicate keeps its first provenance and fails the
   manifest run).
6. **No use of the word "recall" for PII**, in the template or in a report made
   from it.

The figures for this pilot (12 documents, 155 pages, 2 pages without a text
layer, no scans) go into the report made from the template, not into the
template.

No code changes. The docs change: `docs/reference/evaluation.md` points at the
template, and `docs/index.md` links it.

## Non-goals

- **Filling the gate slots.** Only Mark does; nothing here writes his
  questions or his read.
- **Recording provenance on re-delivery**, and **repairing the 567-document
  dossier.** Both are findings the report states, not work in this change.
- **Enforcing in software who fills a slot.** A markdown template cannot; see
  design.md.
- **The gold-set tooling**, a separate change.

## Open questions

- **Where the template lives.** design.md proposes
  `docs/explanation/pilot-report-template.md`; the channel did not decide it.
- **What the report says if Mark's slot stays empty.** This change says the gate
  is reported as "not yet run", never as passed. Whether an unfilled report may
  be published at all is Mark's call.
