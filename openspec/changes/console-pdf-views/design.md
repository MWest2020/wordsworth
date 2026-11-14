# Design: console-pdf-views

## Decisions

- **Links, not a viewer.** The browser opens a PDF; an embedded viewer adds a
  dependency and a CSP exception for nothing.
- **Same gates.** The browser calls the API routes themselves
  (`GET /documents/{id}/redacted.pdf`, `POST /documents/{id}/reveal.pdf`) with
  the console cookie, as the text reveal already does; the console adds no route
  and no authorisation code of its own. The reveal PDF stays uncached and
  audited; the page holds it as an in-memory blob only.
- **Availability, not permission, on the page.** `console_pdf.state` reads
  whether the redacted PDF would be served (a box map, made under the current
  detection lists: `pdf_redaction.box_map_status`, the one function the route
  also calls; and an object store, without which the routes do not exist) so
  the page links it or names the reason. It never decides who may fetch it.
