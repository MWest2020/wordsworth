# Change: allowed-host-stays-whole

## Why

Issue #157, follow-up to #124. After reprocessing, 133 web addresses in 90
documents read `https://www.[LOCATION:…].nl` or similar: an address that
`allow.json` says may stay readable, with a name inside it replaced anyway.

Measured 2026-09-23 against the originals: every one of these sits on an
allowed host (the 13 with a readable path all do). The cause is the
replacement step. An allowed address gets no URL detection, and entity
values are replaced **by value, everywhere in the document** — so a name
found elsewhere ("Gooise Meren" in the letterhead as LOCATION, a municipality
name in a sentence) is also replaced inside the allowed host. The exception
says "keep this readable"; the replacement ignores it.

That is too much hidden, not too little. Nothing leaks. But an institutional
address half replaced is neither readable nor useful, which is exactly what
the exception was written to prevent.

Mark, 2026-09-24: treat the allowed address as one unit, through OpenSpec.

## What changes

The **host** of an allowed web address (scheme, `www.`, domain, port) is
protected from entity replacement, in the same way the tokens of the
deterministic layer already are. The **path** is not protected: a name in a
path keeps being replaced as before.

## Not in scope

- Which hosts are allowed. That stays `allow.json`, with a reason per rule.
- Addresses that are not allowed. They become `[URL:…]` as before.
