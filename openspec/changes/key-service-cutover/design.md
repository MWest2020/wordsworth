# Design

Withdrawn; see `proposal.md`.

**Decision:** one directory held the spec deltas of all three parts while the
tasks pointed at sub-changes that did not exist. The architect failed twice on
it.

**Rejected:** restarting the build on the same directory (it fails on the same
cause); keeping the deltas here and adding the sub-changes beside them (two
sources of truth for the same requirements).

**Chosen:** this change carries no deltas and no tasks. The design of the seam,
the switch and the drop belongs to `key-service-cutover-seam`,
`key-service-cutover-switch` and `key-service-cutover-drop`.
