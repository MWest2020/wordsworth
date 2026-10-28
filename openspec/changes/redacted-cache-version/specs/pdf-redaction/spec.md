## MODIFIED Requirements

### Requirement: The redacted PDF is served from a cache that knows when it is stale

`GET /documents/{document_id}/redacted.pdf` SHALL serve the redacted PDF, cached
under `redacted/<doc>/<render_version>/<boxmap_hash>`. The `render_version` SHALL
be a constant of `pdf_render` that is bumped with every change to `pdf_render`,
so that a change of the renderer never serves a render made by an older one. It
SHALL answer 409 `stale` when the current `lists_hash` differs from the one the
box map was made with. The `reanonymize` operation SHALL regenerate the box map.

#### Scenario: A lists change, then stale, then reanonymize

- **WHEN** the detection lists change, the endpoint is called, `reanonymize` is
  run, and the endpoint is called again
- **THEN** the first call answers 409 `stale` and the last call serves a PDF made
  with the new lists

#### Scenario: A new render version misses the cache

- **WHEN** a redacted PDF is cached under one render version and the render
  version then changes
- **THEN** the next call does not read the old object, renders again, and stores
  the result under the key with the new render version
