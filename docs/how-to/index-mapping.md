---
status: current
last_reviewed: 2026-09-18
---

# Adding a field to the search index

`ensure_ready()` creates the index **only when it does not exist yet**. A field
added to `_mapping()` afterwards therefore never reaches an index that is already
there — and that is not a loud failure.

## Why this bites without an error

OpenSearch maps an undeclared field dynamically on first write. A list of strings
becomes `text` with a `.keyword` subfield, not `keyword`. A `terms` filter on the
raw field then matches **nothing**, and the search answers with zero hits and no
error.

That is the worst shape a fault can take here: the answer is wrong and looks
ordinary. It happened on 2026-09-18 with the `dossiers` field — every test was
green, because tests create the index fresh, and the scoped search returned
nothing in production while `dossier=alle` returned nine.

## What the code does now

`ensure_ready()` also **adds fields the mapping has gained** since the index was
created (`indices.put_mapping`) — additive and idempotent, the same shape as the
column migrations in `db.py`.

A field that already exists with the **wrong type** raises `MappingConflict`.
Deliberately hard: a field cannot be retyped in place, and carrying on would
leave a filter that silently matches nothing.

## Repairing an index that already has the wrong type

Reindex into a correctly mapped one. Verified first, then swapped:

```python
cl.indices.create(index="wordsworth-new", body=_mapping(dim))
cl.reindex(body={"source": {"index": "wordsworth"},
                 "dest": {"index": "wordsworth-new"}},
           params={"wait_for_completion": "true"}, request_timeout=180)
```

Check the new index answers the query the old one got wrong **before** deleting
anything — on 2026-09-18 the same search gave 0 on the old index and 9 on the
new, which is what made the diagnosis certain rather than plausible. Then delete
the old index, recreate it from `_mapping()`, reindex back, and drop the
temporary one.

`request_timeout` is the keyword the client wants; `timeout` in `params` raises
`Timeout value connect was 180s, but it must be an int, float or None`.

Search is unavailable between the delete and the reindex. That window is short
and the temporary index holds everything, but it is a window.
