## Why

An unscoped grant (`document_id = NULL`) authorizes reveal on **every** document.
That is the specified behaviour today ("a grant with no document scope authorizes
for any document"), but the authorized security pass of 2026-08-30 showed it is
the wrong default: a single `[PERSON]` grant issued without a scope returned 200
on two different document ids (finding F3, Low/Med).

F3 was mitigated at the *issuer*: the console can now pass `document_id`, and it
renders "scope: **alle documenten**" in bold on an unscoped grant. But the field
is labelled "document-id (optioneel)" — leave it empty and you get a
reveal-everything grant again. The safe path is possible, not default, and
nothing in the core refuses one. `grants.authorize()` still treats
`document_id is None` as "global".

Global grants are a legitimate capability (a bulk-reveal operator task), so the
answer is not to remove them but to make them a deliberate, configured choice.

## What Changes

- **New setting `WORDSWORTH_ALLOW_GLOBAL_GRANTS`, default `false`.** When false,
  unscoped grants are refused at issue and inert at authorize; when true, today's
  behaviour is unchanged.
- **Issue refuses an unscoped grant** (`POST /grants` without `document_id` →
  400) while the gate is closed, so the default path cannot silently produce a
  reveal-everything capability.
- **Authorize is fail-closed for unscoped grants** while the gate is closed: an
  already-issued global grant authorizes the empty set. This is what makes the
  gate a control rather than a UI nicety — a grant issued before the gate, or
  straight into the DB, is also covered.
- **Spec amendment.** The `grants` capability currently *requires* global grants
  to apply to any document. That requirement is narrowed: they do so only when
  the deployment allows them.

Deliberately NOT in scope: removing global grants; a role model on top of grants;
making `document_id` required in the console UI (the 400 already forces the
operator's hand, and the console renders the API error).

### Deviation from the repo's opt-in convention

`WORDSWORTH_API_KEYS` and `WORDSWORTH_CORPUS_READ_LABELS` are both empty-by-
default and inert, so new controls in this codebase have so far defaulted to
"unchanged behaviour". This change deliberately defaults to *denied* instead: the
point of the gate is that the safe path becomes the default one, and an opt-in
gate would leave exactly the hole F3 found. Live check on the homelab deployment
(2026-09-04): 14 grants, of which 6 unscoped and **0 of those active** — so
default-deny changes nothing for any live authorization. A deployment that does
want global grants sets one env var, which is then visible in its configmap.

## Capabilities

### Modified Capabilities
- `grants`: an unscoped ("global") grant authorizes any document only where the
  deployment explicitly allows global grants; otherwise it cannot be issued and
  authorizes nothing.

## Impact

- Code: `config.py` (`allow_global_grants`), `grants.py` (`authorize()` takes the
  allowance and returns the empty set for an unscoped grant when it is off),
  `api.py` (`create_app(allow_global_grants=...)`; 400 on unscoped issue; pass the
  flag through the reveal path). No new dependency, no schema change, no
  migration.
- Behaviour: breaking *by design* for a deployment that relies on active global
  grants — it must set `WORDSWORTH_ALLOW_GLOBAL_GRANTS=true` or re-issue scoped
  grants. Verified above that the homelab deployment has none.
- Audit: unchanged. Grants still carry no key material and no clear PII; a refused
  issue writes no grant and no audit event.
- Tests: unit (unscoped grant inert when off, authorizes when on, scoped grant
  unaffected either way) + API (400 on unscoped issue when off, 201 when on,
  reveal with a pre-existing unscoped grant denied when off) + full suite green.
- Incidental (same seam): `client.py` prints the API's `detail` on an HTTP error.
  Without it every 400 reads as a bare "HTTP 400 Bad Request", which would make
  this refusal unactionable at the CLI; it now also explains the pre-existing
  malformed/naive-expiry 400s.
- Docs: the reveal/grants how-to gains the setting and the bulk-reveal recipe;
  the security-review baton's F3 entry can then cite a structural fix.
