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
- **Builds on `console-hide-deleted`.** The hidden-documents rule and its
  toggle come from that change; this one uses its helper rather than a second
  filter.
