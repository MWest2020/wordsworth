# Design: console-share

Code references are to origin/main `8bbbcec`.

## Decisions

- **No second door.** Every share route calls the guard `POST /grants` calls:
  `_guard_grant_admin` (`api.py:449`), which is `auth.authorize_grant_issue`
  and nothing else. The console already receives it as `admin_guard`
  (`console.py`, `_mag_beheren`, used by the roles page). The form, the issue,
  the list, the result page and the revoke all sit behind it. Refusing is the
  same 403. There is no beheerder path (issue #417).
- **A share is a batch of grants.** `shares.share` calls `grants.issue_grant`
  once per document, so every grant gets its own `grant_issued` event in the
  key-lifecycle stream, exactly as if it had been issued over the API. The
  grants themselves are ordinary grants: `authorize`, the reveal routes and
  `share-recipient-read` treat them like any other.
- **Least by default.** The level defaults to PPL 0 (placeholders only) and the
  expiry to 30 days; raising either is a choice the sharer makes. A share
  always has an expiry: the form does not offer "never".
- **All or nothing.** One share is one transaction: the grants, their audit
  events and the `share_id` commit together or not at all. Everything that can
  refuse (the gate, validation, the index read for a topic) happens before the
  first row is written.

## Storage

`share_id` is a nullable `VARCHAR` column on `grants`: `GrantRecord.share_id`
in `models.py` and `("grants", "share_id", "VARCHAR")` in `db._COLUMNS`, the
established list for columns added to an existing table. NULL for every grant
issued over the API or the CLI, before and after this change.

No `shares` table. Document deletion deletes the grant rows of the document
(`deletion.py:174-180`); with the id on the grant row it needs no change, and
a share simply holds one grant fewer. A share whose last grant row is gone no
longer exists, and the audit events of its grants remain.

Two consequences, accepted:

- The scope a share was made from (which dossier, which topic) is not stored.
  A share is the documents it was issued for at that moment. The list of
  shares shows the recipient, the sharer, the dates, the level and the number
  of documents, not "dossier X".
- The key-lifecycle events do not carry the share id (`grant_issued` has no
  such field, and "same audit as `POST /grants`" means the same events). The
  trail shows N grants with one actor, one recipient and one moment.

`grants.py` is 359 lines and is not changed. `issue_grant` and the
`GrantStore` protocol keep their signatures; `shares.share` sets `share_id` on
the rows it just issued, in the same session, and raises when a row is not
there (a store that is not the Postgres one), rather than issue a share that
cannot be revoked as one.

## `shares.py`

```
share(session, store, key_audit, scope, recipient, *, ppl=None, role=None,
      expires_at, actor, index=None) -> Share
revoke(session, store, key_audit, share_id, actor) -> int
listing(session) -> list[dict]
get(session, share_id) -> Share | None
```

**Scope to documents.** `scope` is a kind (`document`, `topic`, `dossier`) and
an id. The documents are the live ones, by the console's one hiding rule
(`console_data.hidden_condition` over `latest_state_subquery`):

- document: that document, if it is live;
- dossier: every live member in `dossier_documents`. Its own query, not
  `console_list.documents`: that one stops at `CAP = 200` rows for the page,
  and a share of a 405-document dossier must not silently be a share of 200;
- topic: membership lives in the search index only (`models.Topic`). The
  members are the entries of `index.documents_in(str(topic.dossier_id))` whose
  `topics` hold the topic id, as `topic_labels` reads them, intersected with
  the live members of that dossier in the database, so a stale index entry
  for a deleted document issues nothing.

**Index down.** `documents_in` raises `SearchUnavailable`. It is not caught in
`shares.py`; it is raised before any grant is issued. The console answers 503
with "De zoekindex is niet bereikbaar; er is niets gedeeld." Sharing a document
or a dossier does not read the index and works without it.

**Refused before any write** (each with its own message, none issuing
anything): an empty recipient; both or neither of `ppl` and `role`; `ppl`
outside 0–3; a role that does not exist (as `POST /grants` refuses it); the
role `beheerder`; an expiry that is missing, not timezone-aware or not in the
future; an unknown document, topic or dossier; a scope with no live document.

The beheerder role is refused because `caller_holds_role` counts any active
grant naming it, document-scoped or not: a share "at role beheerder" would
make its recipient someone who may delete documents (`authorize_delete`).
`POST /grants` can still do that, deliberately; a share is not the place.

**Domain.** Each grant is issued on its document's own domain
(`pipeline.document_domain`). `POST /grants` defaults to the default domain; a
share that did the same would issue grants that reveal nothing on a document
of another domain.

**Types.** `ppl` expands through `types_for_ppl`, as `POST /grants` does; a
role is stored as the role name with an empty type list, and resolved at use.

**Revoke.** `revoke` calls `grants.revoke_grant` for every grant of the share
that is still active, and returns how many. Already revoked grants are
skipped: `revoke_grant` writes a `grant_revoked` event even when the store had
nothing to do, so revoking a share twice would otherwise write every event
twice. An unknown share id is a 404. The actor is the caller.
(`POST /grants/{id}/revoke` records the actor as the literal `"operator"`,
`api.py:1878`; that is not changed here and is reported separately.)

**Sharing twice.** A second share of the same documents with the same
recipient issues new grants under a new share id. Revoking one leaves the
other in force. No de-duplication: two shares are two decisions.

## Console

`console_share.py`, mounted from `console.py` like the other pages:

| Route | Does |
|---|---|
| `GET /console/share?document=<id>` / `?topic=<id>` / `?dossier=<name>` | the form: what is shared (name and number of live documents), recipient, level or role, expiry |
| `POST /console/share` | issues, then 303 to the result page |
| `GET /console/shares` | the shares: recipient, sharer, issued, expires, level, active and revoked grants |
| `GET /console/shares/{share_id}` | the result page, also the page of an existing share |
| `POST /console/shares/{share_id}/revoke` | revokes, then 303 back |

All five call the guard first. The share routes mount only where a grant store
is configured, as `POST /grants` does; `api.py` passes the store factory and
the guard to `build_router`.

"Delen" appears on the document, topic and dossier pages only for a caller who
may issue. The page asks the same function: `api.py` gains
`_may_issue(request) -> bool` next to `_guard_grant_admin`, which becomes
"raise 403 unless `_may_issue`". One decision, asked twice. A caller who types
the address anyway gets the 403. The sentence on the document page, "De console
mag er zelf geen uitgeven", goes.

**Result page.** Per document: its name, a link to `/console/documents/{id}`,
and a link to `/documents/{id}/redacted.pdf` when a `BoxMap` row exists, or
"nog geen gelakte PDF" when not (354 of the 415 documents of the pilot dossier
have one). It states the recipient exactly as stored, that the recipient must
be logged in under exactly that name and finds the documents under
`/console/gedeeld`, and that a level above PPL 0 is revealed from the document
page under the recipient's own login. Those links answer 200 for the recipient
because of `share-recipient-read`, and for no other reason.

**No value in any message.** Messages, pages and audit events of a share name
documents by label and id, and counts. None carries a PII value from a
document; the form has no free-text field besides the recipient.

## Line counts

| File | Lines now | Change |
|---|---|---|
| `shares.py` | new | under 200; if scope selection does not fit, it moves to its own module |
| `console_share.py` | new | under 200 |
| `grants.py` | 359 | none |
| `auth.py` | 167 | none |
| `models.py` | 407 | + the column on `GrantRecord` |
| `db.py` | 205 | + one line in `_COLUMNS` |
| `api.py` | 2009 | `_may_issue`, and two arguments to `build_router` |
| `console.py` | 233 | one `mount` call and its parameters |
| `templates/` | | `share.html`, `share_result.html`, `shares.html` new; a "Delen" link in `document.html`, `dossier.html`, `topics.html` |

The four files over 200 already are touched at call sites only. Tests go in
new files (`tests/test_console.py` is 518 lines).
