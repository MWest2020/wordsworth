---
status: draft
last_reviewed: 2026-10-28
---

# Pilot report: Gooise Meren Woo-publicatie 2022

A copy of the [pilot report template](pilot-report-template.md) for the
dossier "Gooise Meren Woo-publicatie 2022" (`f42ab3e1-d61f-4d59-be3a-6c071ad8a9f0`).
This first version commits **only the ranking questions and their expected
documents**, before any search is run (section 3). The other sections and the
results follow in a later commit; its time against this commit's time is the
proof of the order.

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

| # | question | expected document |
| --- | --- | --- |
| 1 | Hoeveel opvangplekken moet de regio realiseren volgens de taakstelling van de spreidingswet, en hoe ziet de tijdlijn per locatie eruit? | `f7a104e2-55ad-401f-a0a5-ec558499fe0d` |
| 2 | Welke brieven gingen naar de wijk over de noodopvang van asielzoekers, en wanneer zou het persbericht uitgaan? | `ff52c6c4-cae8-4e07-b034-7c8f273e326a` |
| 3 | Hoe zijn de 97.000 opvangplekken volgens de verdeelsleutel over de provincies verdeeld? | `fdcd3183-f032-4e34-843e-4d29f159514b` |
| 4 | Welke belemmeringen voor de opvang van asielzoekers kaart de gemeente aan in haar brief over de aanpak daarvan? | `5e26ada3-283a-41ff-b0c7-14fc01993a69` |
| 5 | Wat adviseerde de omgevingsdienst over het milieukader bij de omgevingsvergunning voor de wijziging van de bestemming? | `103aea94-9217-4f2f-a07e-a608136dde08` |

The gate (template): the expected document in the top 8 for at least 4 of the
5 questions. The search will be the API's dossier-scoped search
(`GET /search?q=<question>&dossier=Gooise Meren Woo-publicatie 2022`), the
question text as typed above.
