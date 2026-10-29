# Design: console-dossier-home

## Decisions

- **Dossier first, because every other job needs one.** Search already
  refuses to run without a dossier (`console_search.py`); topics are per
  dossier. The home page asks that question first instead of listing documents.
- **One dossier → no picker.** An installation with one dossier (today's) opens
  on it; a picker with one choice is a click with nothing to decide.
- **Reuse, don't fork.** The question box posts to the existing
  `/console/search` with `dossier=`; topic links use the existing `topic=`.
  The dossier page adds no ranking of its own.
- **Builds on `console-hide-deleted`, built first.** The hidden-documents rule
  and its toggle come from that change; this one uses its helper rather than a
  second or local filter. The dependency is stated in the proposal; the build
  does not start before that change is built.
- **`?dossier=<name>`, not a path segment.** Every other console page takes the
  dossier as a query parameter. Names are free text: a name with a slash makes
  `/console/dossiers/{name}` match no route, so the 404 that lists the dossiers
  is unreachable for it, and a space needs encoding. A query parameter has
  neither problem.
- **New module for the new routes.** `console.py` (255 lines) and `dossiers.py`
  (216) are already over the 200-line limit of the contract and must not grow.
  Home and dossier page go in `console_dossier.py`.

## Rejected alternatives

- **`/console/dossiers/{name}`.** Breaks on slashes in names (see above) and is
  the only console page that would address a dossier differently.
- **A local filter for deleted documents on the dossier page.** A second copy of
  the rule that would drift from `console-hide-deleted`.
- **Adding the routes to `console.py` or `dossiers.py`.** Both are over 200
  lines already.
