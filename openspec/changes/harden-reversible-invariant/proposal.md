## Why

An adversarial audit of the Fase-B reversible stack found a HIGH-severity,
fail-**open** leak: `ReversibleAnonymizer` substituted GLiNER entities by the
service's `(start, end)` offsets, and silently dropped any span whose offsets did
not match a Python character slice (byte-vs-char on non-ASCII Dutch text — é/ë/ï
— or chunk-boundary spans). The clear name then remained in `anonymized_text` →
the search index → `/export/anonymized.zip`, with no exception raised. This
breaches the cardinal invariant (no clear PII in the index) on the most PII-dense
entity type. The audit also flagged smaller hardening items.

## What Changes

- **Offset-independent entity redaction (the fix).** Entity substitution now
  matches the literal detected VALUES in a single longest-preference pass (all
  occurrences), never the reported offsets — so an offset mismatch cannot leave
  clear PII behind, and multiple occurrences and chunk-boundary spans are all
  covered. **Defense-in-depth:** after substitution, inserted tokens are stripped
  and if any detected value still remains the driver **fails hard**
  (`AnonymizationEngineError`) rather than emit possibly-clear text.
- **Revealable multi-word types.** The pseudonym token regex accepts `[A-Z0-9_]+`
  labels, so types like `PHONE_NUMBER` are matched and thus revealable (previously
  silently un-revealable).
- **Reveal access attribution.** The `deanonymize` audit record now carries the
  authorising `grant_id` (via an `extra_audit` hook); the reveal route documents
  that it is tailnet-internal and the `grant_id` is a bearer capability (full
  caller authentication remains a separate, flagged decision).
- **Leaner failure audit.** `profile`/`extract` FAILED audit payloads record the
  error TYPE, not a raw pypdf message that is not guaranteed to be text-free.
- **Robust expiry check.** `authorize` treats a tz-naive `expires_at` as UTC so a
  reveal can never 500 on the comparison (fail toward denial).

## Capabilities

### Modified Capabilities
- `pseudonymization`: reversible entity redaction is offset-independent and
  fail-hard if any detected value could survive; reveal access is attributed to
  the authorising grant.

## Impact

- Code: `pseudonymizer.py` (`_pseudonymize_entities` rewrite, widened token regex,
  `deanonymize` `extra_audit`), `api.py` (reveal passes `grant_id`), `pipeline.py`
  (error type only), `grants.py` (tz-safe expiry). No schema change; no new dep.
- Tests: offset-independence (bogus offsets → no leak), all-occurrences redaction,
  underscored-type revealable, grant_id in the reveal audit. Local suite 229
  passed.
- Not addressed here (flagged follow-ups): single-active-key enforcement + a
  process-lifetime key provider (perf/cache); full caller authN is a decision for
  the operator.
