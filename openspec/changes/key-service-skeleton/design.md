# Design

The service reuses the existing modules behind their seams; what is new is the
process boundary, the database, the API and its authentication. The service's
schema is created by its own init entrypoint. It never accepts a caller
identity from a header: the assertion is verified with the same `Identity`
code wordsworth uses. A homelab manifest (separate PR in MWest2020/homelab) runs
it with a NetworkPolicy that admits only wordsworth's pods.
