# Design

The copy runs with wordsworth in maintenance for writes (ingest and grant
changes paused; search and the console stay up), so the copied state is
consistent. Verification is the gate: a mismatch aborts, leaves wordsworth on
the old drivers, and reports counts. The verification never prints a value: it
compares decryptions in memory and reports equal/unequal counts.
