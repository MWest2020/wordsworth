# Put a render version in the cache key of redacted PDFs

## Why

The orchestrator, from the odin coding session: *"redacted-pdf-size works
(00213a91: 151 MB → 12.5 MB), but only after I emptied the cache by hand. The
cache key redacted/<doc>/<boxmap_hash> doesn't change when the renderer does,
so old renders (the 151 MB one, and before #257 even one that hid nothing) keep
being served."*

The cache key is derived from the box map only. A change to `pdf_render` (the
size fix, the degenerate-box fix) leaves every key unchanged, so the cache keeps
answering with a render the current code would no longer produce. That is a
promise: what `redacted.pdf` serves is what the current renderer makes. A render
that hid nothing must never be served again after the renderer is fixed.

This changes what the cache guarantees, so it is an OpenSpec change.

## What changes

- The cache key becomes `redacted/<doc>/<render_version>/<boxmap_hash>`.
- `render_version` is a constant owned by `pdf_render`, bumped with every change
  to `pdf_render`, so a renderer change never serves an old render.
- Old objects under `redacted/<doc>/<boxmap_hash>` are never read again; they
  are orphaned, not served.
- A test proves that a different render version misses the cache.
- A runbook note on clearing old prefixes.

Not changed: the reveal PDF (never cached), the 409 `stale` rule, the box map
and `boxmap_hash`.

## Open questions

- How "bumped with every change to `pdf_render`" is enforced. The decision says
  it is bumped; it does not say whether anything fails when someone forgets. A
  test that pins a hash of the `pdf_render` source would catch a forgotten bump
  but fails on every edit, even a comment. Left to Mark; until decided, the
  bump is a convention stated in the docs, not a checked requirement.
