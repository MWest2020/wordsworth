# Design

## Choices

- **The version goes in the key, not in a check on read.** Key
  `redacted/<doc>/<render_version>/<boxmap_hash>`. A new version simply misses
  the cache and renders again. No lookup of the old object, no comparison, no
  deletion needed for correctness.
- **The constant lives in `pdf_render`.** The version is a property of the
  renderer, so it sits next to the code it describes. `redacted_cache_key` takes
  it as part of the key; the endpoint passes nothing new.
- **Bumped by hand with every change to `pdf_render`.** That is the decision.
  Enforcement is an open question in the proposal and is not a requirement here.
- **Old prefixes are orphaned and cleared by runbook.** They cost storage, not
  correctness, because nothing reads them. The runbook says how to clear them.

## Rejected alternatives

- **Emptying the cache by hand after each renderer change.** This is what
  happened; it relies on someone remembering, and a missed step serves a render
  that hid nothing. The clever pitfall: it looks like it works until the one time
  it is skipped.
- **Hashing the `pdf_render` source into the key.** Automatic, but every comment
  edit invalidates every cached render, and the key stops saying which render it
  is. Not what was decided.
- **Storing the version on the box map row.** The box map does not change when
  the renderer does, so it would not move the key.
