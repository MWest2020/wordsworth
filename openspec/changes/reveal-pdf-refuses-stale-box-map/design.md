# Design: reveal-pdf-refuses-stale-box-map

Closes #438. Code references are to origin/main `8577ece`. Builds on
`reveal-authorize-first` (PR #494), whose words are used here: a caller is
**covered** when `grants.authorize()` returns a non-empty set for the grant
and the document, its domain included, and the VC gate (where configured)
admits him; anyone else gets the **uniform refusal**.

## Context

- `pdf_redaction.box_map_status(session, document_id, lists_hash)` returns
  `(box_map, None)`, `(None, NO_BOX_MAP)` or `(box_map, STALE)`. It compares
  the box map's `lists_hash` with the lists as configured now
  (`current_lists_hash()`), not with the document's own audit trail.
- It has two callers: `GET .../redacted.pdf` and the console's PDF block
  (`console_pdf.state`). The reveal PDF is the third place a box map is used
  and the only one that does not call it.
- In `reveal_pdf`, `deanonymize()` runs before the render. It decrypts the
  mappings and writes the audit record; the commit comes after the render.

## Decisions

### 1. One check, three callers

The reveal PDF calls `box_map_status` with `current_lists_hash()`, as the
redacted PDF does, in place of `session.get(BoxMap, ...)`. The function
already answers both "no box map" and "stale", so the route gets both from
one call and cannot disagree with the console's button.

Once #494 is built the call sits in `reveal_gate.decide(..., pdf=True)`,
where its `if pdf and no box map` line is.

Alternative: a second comparison written into the route. Rejected: that is
how the two PDF routes came apart.

### 2. The same answer as the redacted PDF

409, body `{"detail": "stale"}`. The console and any client that handles the
redacted PDF's refusal handle this one without a change, and `reanonymize` is
the remedy for both.

Alternative: a longer sentence. Rejected: two spellings of one condition.

### 3. Refuse, with no way round

No flag, no header, no "serve anyway with a warning". A reveal PDF over a
stale map shows values in clear that the caller has no grant for; a warning
does not put the box back. The contract's rule is no silent fallback, and a
PDF that looks redacted and is not is the silent kind.

Cost: a lists change makes every reveal PDF answer 409 until its document is
reprocessed (about 25 hours of GLiNER for the whole pilot corpus, per
`api-corpus-read-gate`'s design). The text reveal is not affected, so a
recipient is not locked out of the content his grant allows.

**The clever pitfall.** Rebuilding the box map inside the request ("it is
stale, so refresh it and serve"). That runs detection in the request path,
turns a read into a write on the document's audit chain, and has to answer
`value-not-located` somehow when a value cannot be boxed. `reanonymize` is
the one place a box map is made; it stays the only one.

A second pitfall, already named in `box_map_status`'s docstring: comparing
against the hash in the document's own `anonymize` record. Those two are
equal by construction, so the check would never fire.

### 4. Where it comes in the order

For a covered caller, after #494's answers about the document and before
anything is revealed:

1. grant, domain, VC gate (uniform refusal or `vc rejected`), per #494;
2. 410 deleted; 409 superseded; 409 no box map; **409 `stale`**; 409 not yet
   de-identified;
3. only then: types, `deanonymize()`, the original, the render.

`stale` directly follows "no box map" because one call decides both. It comes
before `deanonymize()` on purpose: a refused request must not decrypt a
mapping or lean on the transaction rollback to keep the audit chain clean.
The spec says so in terms of the result (no record, nothing decrypted), not
of the call order.

### 5. An uncovered caller hears nothing

`stale` says the document exists, has a box map, and that its lists are
behind. That is an answer about the document, so it follows #494's rule: only
a covered caller gets it. The requirement is written against the outcome ("the
answer he would get if the box map were current"), so it holds on today's
order too, where `authorize()` already runs before the text lookup.

### 6. The text reveal is left alone

`POST /documents/{id}/reveal` substitutes tokens in the stored pseudonymised
text. It has no box map and no "unboxed" value: what the old lists missed is
in clear in that text for every reader already, with or without a grant. That
is the staleness `reanonymize` exists for, and it is not made worse by a
reveal. See "Found and not changed".

## Risks

- **Reveal PDFs go dark after a lists change** until reprocessing is done.
  Accepted (decision 3). Task 4.1 reports the count before the deploy so it
  is not a surprise on the day; the console already says why per document.
- **Replicas with different lists.** `current_lists_hash()` reads the lists
  of the replica that answers. During a rolling deploy that changes the lists,
  one replica can serve and another refuse. The redacted PDF has the same
  property; both settle when the rollout ends. Not changed here.
- **`DegenerateBoxError`** (a box without surface, 409) is still raised by
  the render, after `deanonymize()`; the transaction is rolled back. Left as
  it is.

## Found and not changed

- The text reveal and `GET /documents/{id}/anonymized` serve text made under
  older lists without saying so. A value newer lists would catch is clear in
  it for every reader. Whether the text routes should say `stale` as the PDF
  routes do is a separate promise; not proposed here.
- `tests/test_reveal_pdf_api.py` has no case with a lists change; task 2 adds
  them.

## Open questions

None. The default in #438 decides the behaviour.
