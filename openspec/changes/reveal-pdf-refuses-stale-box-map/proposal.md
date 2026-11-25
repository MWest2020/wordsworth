# reveal-pdf-refuses-stale-box-map

## Why

A box map records where the detected values are on the page. It is made under
one set of detection lists and carries their hash. When the lists change, a
value the new lists detect has no box in the old map.

`GET /documents/{id}/redacted.pdf` knows this and answers 409 `stale`
(`api.py:707-715`, through `pdf_redaction.box_map_status`). `POST
/documents/{id}/reveal.pdf` does not: it reads the box map with
`session.get(BoxMap, ...)` (`api.py:1541`) and never compares the hash
(issue #438, found while building `console-pdf-views`, #436; line numbers at
origin/main `8577ece`).

The reveal PDF is drawn from the original page. A box that is painted hides a
value; everything without a box passes through in clear, pixels and text
layer. So a reveal PDF over a stale box map shows, in clear, every value the
newer lists would have boxed, whatever types the grant allows. A grant for
`EMAIL` then also shows the name that was added to the deny list last week.
The redacted PDF refuses in exactly this situation; the reveal PDF, which
goes to people outside the reader group, does not.

The console already tells the reader: on a stale box map the "Onthul als
PDF" button is disabled with the reason next to it (`console_pdf.py`,
`document.html:96-107`). The API behind the button still serves.

Decision: issue #438 states the default ("reveal.pdf refuses a stale box map
with the same 409 as redacted.pdf, built after the January demo path"). This
proposal is written on it.

## What changes

- `POST /documents/{id}/reveal.pdf` answers 409 `stale` when the current
  lists hash differs from the box map's, with the same check and the same
  body as the redacted PDF.
- The refusal comes before anything is revealed: no mapping is decrypted, the
  original is not read, no `deanonymize` audit record is written.
- Only a caller the grant covers hears `stale`. Anyone else gets the refusal
  he would get with a current box map.
- After `reanonymize` has rebuilt the box map the reveal PDF is served again.

| case, for a caller the grant covers | before | after |
|---|---|---|
| box map made under the current lists | 200, PDF | 200, PDF |
| box map made under other lists | 200, PDF with unboxed values in clear | 409 `stale` |
| no box map | 409 `no box map yet ...` | same |

## What does not change

- `POST /documents/{id}/reveal` (text): it uses no box map.
- `GET /documents/{id}/redacted.pdf`, the console page, the box map itself,
  `reanonymize`.
- Who may reveal and what a grant allows. Every answer `reveal-authorize-first`
  (#487, PR #494) specifies stays as it says; `stale` is one more answer for a
  covered caller, after its 410 and 409s.

## Capabilities

- `pdf-redaction`: one requirement added, "The reveal PDF refuses a stale box
  map". Nothing is modified, so this change and `reveal-authorize-first` do
  not edit the same requirement.

## Depends on / order

- Built after `reveal-authorize-first` (#494): that change moves both reveal
  routes onto one gate (`reveal_gate.py`), and the stale check belongs in it,
  next to its "no box map" answer. Building this first would put the check in
  a route body that #494 then rewrites.
- Not before the January demo path is done (the default in #438).
- Cost, named: after every change of the detection lists, every reveal PDF
  answers 409 until `reanonymize` has run for that document. The text reveal
  keeps working meanwhile. Task 4.1 counts the stale box maps before the
  deploy.

## Out of scope

Refreshing a box map on request; a text reveal over text de-identified under
older lists (design.md, "Found and not changed"); #442 (already specified and
built as `api-corpus-read-gate`, #485); #456 (change
`deleted-document-answers-410`).
