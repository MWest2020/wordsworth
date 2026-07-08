# Design decisions — add-anonymization-adapter

## The seam (driver/protocol pattern)

```python
class Anonymizer(Protocol):
    def anonymize(self, text: str) -> AnonymizationResult: ...

@dataclass
class AnonymizationResult:
    text: str                 # PII irreversibly replaced
    counts: dict[str, int]    # {"bsn": n, "iban": n, "email": n} for the audit
```

The pipeline imports the protocol, not a concrete class. `process()` takes an
injected `anonymizer` (defaults to `DeterministicAnonymizer`). OpenAnonymiser
will be a second class implementing the same protocol — zero pipeline change.

## Interim driver: DeterministicAnonymizer

Only high-precision, deterministic detectors — no ML, so no OpenAnonymiser
reimplementation and no false-positive tuning:

- **BSN**: `\b\d{9}\b` validated by the elfproef (weights 9,8,7,6,5,4,3,2,-1;
  sum divisible by 11) → `[BSN]`.
- **IBAN**: candidate `\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b` validated by mod-97
  (move first 4 chars to end, letters→numbers, `% 97 == 1`) → `[IBAN]`.
- **email**: standard address regex → `[EMAIL]`.

Detection validates before replacing, so a 9-digit number that fails the
elfproef or an IBAN-shaped string that fails mod-97 is left untouched. Counts are
tallied for the audit payload.

**Irreversible** by construction: placeholders carry no reversible mapping. That
is the anonymization contract; reversible pseudonymization is change (b).

## Clear text is never persisted (the privacy property)

Extraction is in-memory. Only the anonymized text is written (`document_texts`).
On resume from `extracted`, the text is re-derived from the source PDF
(deterministic, born-digital) rather than read from a clear-text store. This
makes "no clear PII toward the index" trivially true and minimises clear PII at
rest. `document_texts` is derived working data (mutable is fine); it is NOT the
audit table and holds no PII.

**Clever pitfall rejected:** persisting extracted clear text "for convenience"
(so anonymize can re-read it). It creates a clear-PII-at-rest store we do not
need for irreversible anonymization; re-extraction is cheap and deterministic.

## State flow (unchanged states, real work)

`extractable → (extract, real) → extracted → (anonymize, real) → anonymized → (index, stub) → indexed`

`extract` failing (pypdf raises on text pull) → `failed`, same loud-failure rule
as profiling. Anonymization of already-clean text is a no-op with zero counts —
still advances to `anonymized`.
