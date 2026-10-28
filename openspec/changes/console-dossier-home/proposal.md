# console-dossier-home

## Why

Mark, 2026-10-28: *"The key user wants to find topics quickly, ask targeted
questions, know which documents are relevant, and share"*, and *"I still only
see the deleted files (a key user doesn't care)"*. The review (docs/explanation/review-key-user-2026-10-28.md) found that
`/console` lists the 200 most recently touched documents, all 200 of them
deleted on the live installation, and offers no dossier, no topics and no
question box. A key user starts from a dossier, not from a document list.

## What changes

- `/console` becomes a dossier picker: each dossier with its number of live
  documents and topics. With one dossier, the console opens straight on it.
- A dossier page, `/console/dossiers/{name}`: a question box that searches this
  dossier, its topics (name, number of documents, a link that searches within
  the topic), and its live documents, most recently touched first.
- Deleted and superseded documents are hidden by the rule of
  `console-hide-deleted` (built before this change), with its toggle.
- The old document list stays reachable as "all documents", for operators.

## Out of scope

Topic labels (`topic-labels-llm`), the matching passage
(`search-matching-passage`), PDF links and sharing (`console-pdf-views`,
`console-share`). No API change.
