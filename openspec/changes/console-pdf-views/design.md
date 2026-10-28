# Design: console-pdf-views

## Decisions

- **Links, not a viewer.** The browser opens a PDF; an embedded viewer adds a
  dependency and a CSP exception for nothing.
- **Same gates.** The console's routes call the same handlers as the API, as
  the text reveal already does; the reveal PDF stays uncached and audited.
