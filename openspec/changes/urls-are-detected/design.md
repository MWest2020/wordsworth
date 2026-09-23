# Design — urls-are-detected

## Why not a deterministic detector

`detectors.DETECTORS` is the obvious home (e-mail lives there). But the
deterministic layer runs first and turns its hits into tokens before the lists
are ever applied, so **no list can exempt a deterministic hit**. With a URL
detector there, `gooisemeren.nl` — the municipality's own site, in 54 of the
770 documents — would become a token everywhere, plus its OCR variants
(`goocisemeren.nl` in 12, `qooisemeren.nl` in 6). That is the over-detection
`restwaarden` measured as the real problem, made worse.

Putting an installation's hosts in `detectors.py` would fix that and put one
municipality's domain in code that every installation runs. Wrong place.

## Why deny + allow

The street address went the same way (PR #141): a `deny.json` rule, reviewable
in the repo, with a reason. The lists are per installation (`/app/lists`,
baked into the image) and are loaded in production.

## Allow over deny, for the same type

`DetectionLists.apply` today: allow removes incoming detections of its type
whose value fullmatches; deny then appends its own matches. So allow never sees
a deny match. The change: deny matches go through the same allow filter.

Why this is safe to change:
- Allow still never crosses types. A `URL` exception cannot touch a `LOCATION`
  match.
- Existing allow rules fullmatch whole values. The existing deny rule matches
  `street + number`. Measured before merging: re-running the lists over every
  stored document with the old and the new `apply` gives the same result for
  every type except `URL`.

## Where an exception comes from

Not a guess. Every host that recurs in the stored corpus was looked at; the
public ones went in with a reason. A host that appears in one document is not
excepted, because that is precisely the shape of a party's own site.

## Reprocessing

The stored text only changes when it is processed again. Same procedure as the
other detection changes: image with the new lists, then reprocess.
