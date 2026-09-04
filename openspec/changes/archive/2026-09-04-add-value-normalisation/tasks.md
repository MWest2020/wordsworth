## 1. Rules

- [x] 1.1 `src/wordsworth/normalization.py`: `PROFILE_VERSION = "n1"`,
  table-driven `normalize(label, value)`; default trim+NFC; BSN strip `.`/space
  + lpad 9; POSTCODE strip space + upper; PERSON/LOCATION/ADRES/ORGANIZATION/EMAIL trim+NFC+casefold;
  DATE → ISO 8601 when parseable else default. Unit tests per rule.

## 2. Derivation + storage

- [x] 2.1 `pseudonymizer.py` derives the token from the normalised value;
  ciphertext still holds the original.
- [x] 2.2 `pii_mappings.norm_version` column (nullable → legacy), written on put.
- [x] 2.3 Runbook step: reprocess after a profile bump.

## 3. Gate

- [x] 3.1 Test: `Jansen`/`jansen` and `1234.56.789`/`123456789` collide;
  reveal returns the original spelling. Suite + CI green; `openspec validate`.
