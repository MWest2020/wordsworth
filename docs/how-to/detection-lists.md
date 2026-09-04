---
status: draft
last_reviewed: 2026-09-03
---

# Runbook: detection allow/deny lists and feedback

Detection is refined by two **git-versioned JSON files** — no rules engine, no
auto-learning. Their content hash lands in every de-identify audit record
(`lists_hash`) so you can always tell which rule version produced a document.

```
WORDSWORTH_DETECTION_LISTS=/etc/wordsworth/lists   # directory with the two files
```

`allow.json` — typed patterns whose **full match** is *not* PII of that type. A
detection is dropped only when its type matches the key (never across types):
```json
{"PERSON": ["^Jansen BV$", "^Gemeente Haarlem$"]}
```
`deny.json` — typed patterns that *are* PII; each match becomes a detection
(layer `list`, score 1.0) on top of what the detectors found:
```json
{"KENTEKEN": ["\\b[A-Z]{2}-\\d{3}-[A-Z]\\b"]}
```

Where it applies: the reversible driver applies both lists after detection; the
irreversible OpenAnonymiser driver applies the **deny** list only (the service
redacts server-side, so an allow rule cannot un-redact). Suppressions are
counted per type in the audit aggregates under `suppressed_by_list`.

## Feedback

A reader who spots a false positive or a miss records it against the document:
```
curl -XPOST $API/documents/<doc>/feedback -H 'content-type: application/json' \
  -d '{"kind":"fp","type":"PERSON","token":"[PERSON:3fa9c2d1]"}'
```
`kind` is `fp` or `fn`; `token` is the `[TYPE:hash8]` pseudonym concerned (for
`fp`). There is **no free-text field**: feedback can never carry a clear value.
The call appends a `detection_feedback` access event to the document's audit
chain and changes nothing else. Turning feedback into a list entry is a
reviewed git change; after changing the lists, run `POST /reprocess` if the
already-indexed corpus should follow.
