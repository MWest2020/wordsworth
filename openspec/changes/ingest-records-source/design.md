# Design: provenance at ingest, and the published-dossier pilot

## Provenance

- **Where it is stored.** `source_url` and `fetched_at` are stored on the
  document row, and repeated in the ingest audit record, so the chain proves
  them. `source_sha256` is the sha256 of the uploaded bytes, the same value
  the object key already carries.
- **Validation.** `source_url` must be `https://` with a host, and at most
  2048 characters. Otherwise the request fails with `400` and the reason.
  `fetched_at` must be ISO-8601 with a timezone. Neither field is required.
- **Why wordsworth computes the hash.** A client-supplied hash would only
  repeat what the client claims.

Rejected: making `source_url` required. Unpublished documents have none, and
requiring it would break the direction Mark set.

## The pilot (published documents only)

| part | what |
|---|---|
| corpus | one Gooise Meren publication as one dossier, 10 to 30 real documents, fetched by hand; the pilot report records who checked robots.txt and the terms, and when |
| ranking gate | at least 5 questions, each with its expected document, written by a person **before** any result is seen; pass when the expected document is in the top 8 for at least 4 of 5. This gates this pilot only and says nothing about general quality |
| PII gate | a person reads the full `/anonymized` text of every pilot document against the source; any residual direct identifier of a private person (BSN, IBAN, e-mail, phone, name, home address) fails the pilot, unless that document is excluded with the reason written down |
| also reported, not gates | residual count, placeholder count, the ORGANIZATION over-redaction rate; officials' names without a public role, as a separate finding |
| a layer that did not run | counts as failed, for example a NER backend that is down |

**Gold set.** The gold set holds offsets and hash only (`sha256, start, end,
type`) and no PII text in git. That works only because a published source can
be rebuilt from the public PDF. The rule must not be generalised: unpublished
documents need their own data-handling decision.

**Officials' names** (architect's call): a private person is a residual; an
official without a public role is reported as a finding; a public office
holder is not a residual. Where that line falls in a given document waits for
Mark or the municipality.

## Tests the reviewer requires

The change touches a seam, so the tests call both ends:

1. **Fields reach the record.** An integration test posts to `/ingest` with
   `source_url` and `fetched_at`, and asserts that both, plus
   `source_sha256`, appear on the document **and** in the audit record.
2. **Omission changes nothing.** Omitting the fields gives exactly today's
   result.
3. **Bad input is refused.** A malformed `source_url` returns 400 with the
   reason.
4. **No text, no index entry.** A PDF with no text layer whose OCR yields no
   text ends in a visible error state, and nothing is indexed.
