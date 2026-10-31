# Design

## Decided

- **Separate change, after the rule.** Re-anonymising is an operation on the
  corpus; the rule is a detection change. The breaker stopped
  `detect-dutch-particle-names` after three builds without a merge, so the
  operation is split off. It builds only after that change has merged.
- **Reuse reprocess.** `wordsworth/reprocess.py` already writes the failure
  trace, continues on failure and is shared by the endpoint and the Job. A second
  loop would drop that trace, as the 2026-09-20 Job did.
- **Count-only check.** Before and after, the number of detected entities per
  type is logged. Never a value, never the text around it, never an offset. This
  follows the existing requirement that no measurement logs a value.

## Rejected

- **A check that shows the old and new text side by side.** It would print the
  very name the rule is about.
- **Folding this into `detect-dutch-particle-names`.** That is what stalled it.

## Open

See the proposal: which documents are affected, where the "before" count comes
from, who runs it. None of these is a requirement.
