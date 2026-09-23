# Change: urls-are-detected

## Why

Issue #124: `www.eazwind.nl` survived pseudonymisation while `info@eazwind.nl`,
two lines above it, became `[EMAIL:…]`. Same domain, two forms, one covered.

Measured 2026-09-23 against the running OpenAnonymiser and the stored corpus:

- **Nothing in the pipeline detects a URL.** The service never emits a `URL`
  entity; wordsworth sends no label list; the deterministic layer knows BSN,
  IBAN, e-mail and postcode; `deny.json` has no URL rule. `URL` exists in
  `pii_categories` as a type that no detector produces.
- **A name inside a URL is only caught by context.** In a synthetic letterhead
  with the company name as its heading, GLiNER tagged `eazwind` inside the URL
  as ORGANIZATION at 0.60. The same URL alone, in a sentence, or with
  `https://`: nothing. And in the real document the heading was never detected
  as `Eazwind` at all — the tokens there are OCR fragments of a logo (`Teaz`,
  `EAZ`; see `restwaarden`). So context would not have saved it either.
- **In the 770 stored documents:** 249 contain a URL. Of the hosts that are not
  obviously public, 35 appear in exactly one document, and 25 documents carry
  at least one such host. Those are the strongest candidates for a party's own
  site, like this one. Lower bound 25 documents, upper bound 227.

Mark, 2026-09-23: a URL detector with an explicit list of public hosts it
leaves alone, then reprocess the corpus.

## Not this again

`restwaarden` proposed an invariant — "a pseudonymised value appears nowhere
else in the document" — and its own measurement withdrew it: the values that
"survived" were ordinary words wrongly tagged as PII (`locatie`, `bewoners`),
and enforcing it would mangle text. This change does not revive it. It does
not depend on the name being detected anywhere; it detects the URL itself.

`restwaarden` also rejected "a deny pattern on every URL", because
`www.rijksoverheid.nl` is not personal data. That objection stands, and is
exactly what the allow exceptions below answer.

## What changes

1. **The evaluation corpus first** (the repo's own rule: what counts as PII
   changes in the corpus before the detector). A party's website is seeded as
   `URL` gold; a government URL is seeded as plain text that must not be found.
2. **A `deny.json` rule for web addresses**: `http(s)://` or `www.` followed by
   a host, excluding trailing punctuation.
3. **`allow.json` exceptions per host, each with a reason**: national public
   references, and the institutions that recur in this installation's corpus
   (the municipality — including OCR-garbled spellings of its own domain — the
   regional environmental service, the province).
4. **Allow wins over deny for the same type.** Today `allow` only filters what
   the detectors found and `deny` adds its matches afterwards, so no allow rule
   can exempt a deny match. That ordering is why the exceptions need this.
5. Reprocess the stored corpus.

## What it costs

More tokens in a system whose measured problem is *over*-detection (39% of
entity tokens start with a lowercase letter). Every URL not on the list becomes
a token, including OCR-garbled ones nobody listed. The exceptions keep the
institutional URLs readable; the rest is the safe direction the lists already
take: a rule too many hides something that was not PII, a rule too few leaves
PII in the text.
