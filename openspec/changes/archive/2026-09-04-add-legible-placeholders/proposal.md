## Why

The target architecture shows the public/PPL 0 view of a document with legible,
numbered placeholders — `[PERSOON 1]`, `[ADRES 1]`, `[BSN 1]` — one counter per
type per document. wordsworth stores and indexes `[PERSON:3fa9c2d1]` tokens,
which are correct for cross-document linkability but unreadable for a Woo
reader or a case worker. ADR-0004 already names legible pseudonyms as a planned
concern and the demo/console sites fake it client-side. It belongs server-side,
once, as a **view** over the stored text — never as a change to what is stored
or indexed.

## What Changes

- `GET /documents/{id}/anonymized?view=legible` renders the stored
  de-identified text with per-document ordinals: the first distinct PERSON token
  becomes `[PERSOON 1]`, the second `[PERSOON 2]`, etc. Same token → same
  ordinal within the document. Type labels are Dutch via a small map
  (`PERSON→PERSOON`, `LOCATION→LOCATIE`, `BSN→BSN`, …; unknown → uppercase type).
- Default view is unchanged (`view=tokens`), so nothing downstream breaks.
- The response includes `legend: {"[PERSOON 1]": "PERSON:3fa9c2d1", ...}` so a
  caller with a grant can still reveal via the token (reveal works on tokens,
  not ordinals).
- ZIP export gets the same `?view=legible` switch.

## Capabilities

### Modified Capabilities
- `reveal-api`: `/anonymized` and the corpus ZIP export offer a legible view.

## Impact

- Code: `legible.py` (pure, ≤ 80 lines), `api.py` two query params.
- Not touched: stored text, index, tokens, mappings, reveal.
