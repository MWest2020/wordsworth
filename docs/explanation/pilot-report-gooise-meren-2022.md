---
status: current
last_reviewed: 2026-10-28
---

# Pilot report: Gooise Meren Woo-publicatie 2022

A copy of the [pilot report template](pilot-report-template.md) for the
dossier "Gooise Meren Woo-publicatie 2022" (`f42ab3e1-d61f-4d59-be3a-6c071ad8a9f0`),
filled in on 2026-10-28 by the coding session. Mark delegated both of his
slots (ranking and PII) by mail that day: "you can fill in the pilot template;
you understand exactly what I want." Every place that delegation matters is
said where it applies.

## 1. The check

There is no `check.json` for this corpus. The 2022 set was loaded by hand in
August 2026, before the pilot ingest with manifest and fetch check existed
(`docs/reference/ingest.md`). Its source URL per document was never recorded.

| field | value |
| --- | --- |
| `checked_by` | none: no fetch check for this corpus |
| `checked_at` | none |
| `robots_txt` | not checked |
| `anubis` | not applicable (not fetched by the pilot) |
| `decision` | none; the corpus was chosen by Mark (2026-10-24) as the pilot publication |

This is a provenance gap, not a pass: the report cannot say where each document
came from beyond "the Woo publication of Gooise Meren from 2022".

## 2. The corpus

Measured on 2026-10-28 from the stored PDFs (pypdfium2), live documents only.

| field | value |
| --- | --- |
| number of documents | 415 (408 indexed; 173 retired duplicates not counted) |
| number of pages | 2,821 |
| pages without a text layer | 14 |
| scans | 6 documents mostly without a text layer; 5 went through OCR recovery |

4 PDFs could not be opened by pypdfium2 and are not in the page counts.

## 3. The ranking-gate slot

**Who wrote the questions.** Not Mark. Mark delegated this slot to the coding
session by mail on 2026-10-28 ("you can fill in the pilot template; you
understand exactly what I want"). The questions are therefore not an
independent human ground truth: they test whether wordsworth finds a document
the question was written *from*, which is easier than a key user's own,
unseen question.

**How they were made (known-item).** The dossier's documents have no
filenames (the 2022 set was loaded by hand in August), so expected documents
could not be picked from a document list. Instead: a seeded random draw
(`random.Random(20261028)`) over the 299 live documents with more than 1,500
characters of text; the anonymised text of the first drawn documents was read;
a question a key user (journalist, council member, Woo officer) would ask was
written for each, paraphrased rather than copied, in Dutch, as such a user
would type it. Two drawn documents were skipped: one because its subject was
too generic to name an expected answer (`138f4f9f`), one because it overlapped
with another drawn document (`d2e66000`). No search had been run when this was
committed.

- Questions committed at: 2026-10-28T23:15:59+01:00 (commit `12901e9`, merged
  to main 23:20:55 as `988955d`, PR #282)
- Time of the first search: 2026-10-28T23:21:09+01:00

| # | question | expected document |
| --- | --- | --- |
| 1 | Hoeveel opvangplekken moet de regio realiseren volgens de taakstelling van de spreidingswet, en hoe ziet de tijdlijn per locatie eruit? | `f7a104e2-55ad-401f-a0a5-ec558499fe0d` |
| 2 | Welke brieven gingen naar de wijk over de noodopvang van asielzoekers, en wanneer zou het persbericht uitgaan? | `ff52c6c4-cae8-4e07-b034-7c8f273e326a` |
| 3 | Hoe zijn de 97.000 opvangplekken volgens de verdeelsleutel over de provincies verdeeld? | `fdcd3183-f032-4e34-843e-4d29f159514b` |
| 4 | Welke belemmeringen voor de opvang van asielzoekers kaart de gemeente aan in haar brief over de aanpak daarvan? | `5e26ada3-283a-41ff-b0c7-14fc01993a69` |
| 5 | Wat adviseerde de omgevingsdienst over het milieukader bij de omgevingsvergunning voor de wijziging van de bestemming? | `103aea94-9217-4f2f-a07e-a608136dde08` |

The search was the API's dossier-scoped search
(`GET /search?q=<question>&dossier=Gooise Meren Woo-publicatie 2022`), with the
question text as typed above.

| # | expected document found in top 8? | rank |
| --- | --- | --- |
| 1 | yes | 1 |
| 2 | yes | 2 |
| 3 | yes | 1 |
| 4 | yes | 2 |
| 5 | yes | 1 |

**Outcome:** passed, 5 of 5 (the gate asks 4 of 5). Read it for what it is: a
known-item test with questions written from the documents themselves, by the
coding session. It shows that a well-phrased question about a document finds
it; it does not show that a key user's own, unseen question finds the right
documents. Mark's own questions would still be the stronger test.

Two observations from the runs: where the expected document was second, the
first hit was a document on the same subject (a sibling letter or a related
memo), which a reader would also want; and words the anonymiser over-detects
(section 5) are not searchable, because the index holds the anonymised text.

## 4. The PII-gate slot

Read by the coding session under Mark's delegation of 2026-10-28, without
revealing anything (no grant, no reveal): the anonymised output only.

**Sample.** 15 documents, seeded draw (`random.Random(20261029)`) over the 408
live documents with text: `acdfaa73`, `8cd9c379`, `496a8265`, `c8b41846`,
`6ec1e7f1`, `91ccfdb0`, `5a17027f`, `3a671e86`, `e33ab168`, `d74999f3`,
`90214d28`, `da7c415d`, `89341960`, `1c87f856`, `fcba7608`.

**Method.** Pattern checks on the anonymised text for e-mail addresses, phone
numbers, IBANs, BSNs (with the eleven-test), postcodes, a title followed by a
name ("de heer", "mevrouw", "dhr.", "mw."), and capitalised name pairs; every
hit judged in its context. Values are not written here, only counts and shapes.

| document | leftover identifier found | excluded (reason) |
| --- | --- | --- |
| `1c87f856` | yes: one full name of a person (shape `<first name> ter <last name>`), most likely an official, in a meeting agenda | no |
| the other 14 | no | — |

Hits that were not identifiers: 10 postcodes, all of an organisation's PO box
("Postbus …"); 4 nine-digit numbers that are case and document numbers. No
e-mail address, phone number, IBAN, BSN or title-plus-name survived in the
sample.

**Outcome:** 14 of 15 documents pass; `1c87f856` fails on one leftover name.
No figure for how much PII was found is claimed, and the word for it that the
template forbids is not used: the source documents were already redacted by the
municipality (the "5.1.2e" boxes), so there is no unredacted original to
measure against.

**Over-redaction** (the other direction, not part of the gate): token density
varies from about 9 to 98 tokens per 100 words in the sample; ordinary words
are tokenised as organisations, places or dates ("statushouders", "bewoners",
"juni" were seen on a rendered redacted page on 2026-10-26). This hurts both
reading and search; the change `redaction-overdetection` is open for it.

## 5. Findings so far

- **Provenance.** This corpus has no source URL per document and no fetch
  check (section 1). The often-quoted "567 documents" was the count before
  duplicates were retired; 415 are live.
- **Duplicates keep their first provenance.** A document delivered again keeps
  its first recorded provenance and fails the manifest run
  (`docs/reference/ingest.md`, "Read-back: the proof, not a re-run").
- **Redacted PDFs.** 354 of 415 documents have one. 51 have none because a
  value could not be located on the page, plus one where a value survived the
  replacement (issue #259, change `redaction-locate-remaining`); 10 have no
  reversible tokens. A failure gives no PDF, never a half-redacted one.
- **Over-detection** of ordinary words (section 4), with a cost for search.
- **Topics.** Re-indexing dropped every document's topic until 2026-10-28
  (change `reindex-keeps-topics`); after recomputing, 17 topics hold 184 of 408
  documents. Their names are frequent terms, not subjects a person recognises
  (Mark: "nietszeggend voor een mens"); naming them needs a language model.
- **The one leftover name** (section 4): the detector missed a full name in a
  meeting agenda.
