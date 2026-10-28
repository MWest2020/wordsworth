# Design

## Decided

- **One span.** First name, particle and last name form ONE `PERSON` detection,
  as street and house number do for an address. Detecting the pieces separately
  leaves a readable particle and a readable half-name, or several tokens for one
  person.
- **Particles of any length.** `van der` is one particle of two words; the span
  runs from the first name to the end of the last name.
- **Proof by shape, not by value.** The test uses synthetic names, one example
  per particle. The check on the real document reports counts only, in keeping
  with the pilot report, which writes shapes and counts and never values.

## Rejected

- **Allow/deny list entries for this name.** A deny rule for one name fixes the
  one document and nothing of the shape; lists are for exceptions, not for a
  detection gap.
- **Redacting every capitalised word pair.** It would swallow ordinary text
  (see the over-detection work in `redaction-overdetection`).

## Left open

Mechanism and the full particle list: see the proposal's open questions. They
are not requirements.
