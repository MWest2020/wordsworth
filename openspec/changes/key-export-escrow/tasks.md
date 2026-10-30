# Tasks

- [ ] Export re-wraps every key of the domain under the receiving key; the
      bundle contains no clear key bytes. Proved by: a test scanning the bundle
      for each key's bytes.
- [ ] Export is refused without a receiving key, with a malformed one, and for
      a non-beheerder; nothing is unwrapped in those cases. Proved by: tests.
- [ ] Round trip: export, import into a second service, and every mapping and
      original of the domain opens there. Proved by: a test.
- [ ] Every export and import is audited without key material. Proved by: a
      test.
- [ ] Docs: `docs/how-to/key-export.md` (escrow, recovery, moving to another
      installation).
