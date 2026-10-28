# Tasks

## 1. The render version
- [ ] A `render_version` constant in `src/wordsworth/pdf_render.py`, and
      `redacted_cache_key` in `src/wordsworth/pdf_redaction.py` building
      `redacted/<doc>/<render_version>/<boxmap_hash>`; the redacted endpoint
      uses it. Proved by: `tests/test_redacted_api.py`, a cached object is found
      under the new key form.
- [ ] A test that changing the render version misses the cache: cache a render,
      change the version, call again, and see a fresh render stored under the
      new key. Proved by: the test in `tests/test_redacted_api.py`.
- [ ] Update the comment on the cache key in `src/wordsworth/models.py` (around
      line 360) and the endpoint docstring in `src/wordsworth/api.py` (around
      line 697), which both name the old key. Proved by: `grep -rn
      "redacted/<doc>/<boxmap_hash>" src` finds nothing.
- [ ] The reveal PDF is still never cached. Proved by: the existing assertion in
      `tests/test_reveal_pdf_api.py` (no object under `redacted/<doc>/`) stays
      green.

## 2. Docs (must change with the code)
- [ ] `docs/how-to/pdf-redaction.md`, "Get the redacted PDF": the new key, that
      the render version is bumped with every change to `pdf_render`, and a
      runbook note on clearing the old `redacted/<doc>/<boxmap_hash>` objects
      (nothing reads them; clearing frees storage). Proved by: the section names
      the key, the bump rule and the clearing step.
- [ ] `docs/how-to/pdf-redaction.md`, "Character boxes" section: the line that
      cached renders were deleted by hand now says the render version makes that
      unnecessary. Proved by: the line is changed.
- [ ] `openspec validate redacted-cache-version --strict` passes.
