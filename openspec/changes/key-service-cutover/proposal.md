# key-service-cutover (withdrawn)

## Why

This change is withdrawn. Nothing is built from it and nothing is archived
from it.

The architect failed on it twice (#559, #561). The cause was this directory:
it kept spec deltas for all three parts of the cutover while its tasks pointed
at sub-changes that did not exist, so a builder had to guess which part was
meant.

## What changes

Nothing. The spec deltas and the tasks are removed. The work moves to three
changes of its own, proposed and applied one at a time, in this order:

1. `key-service-cutover-seam`
2. `key-service-cutover-switch`
3. `key-service-cutover-drop`

Their content, the open questions (#524 on reveal and a signed identity, the
drop of the old tables, who signs the sample reveals) and the dependencies
live in those changes, not here. Do not build this change.
