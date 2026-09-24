# Tasks: allowed-host-stays-whole

## 1. Code
- [x] 1.1 `DetectionLists.allowed_spans(text, type)`: the spans `apply`
      suppresses, one definition.
- [x] 1.2 `ReversibleAnonymizer`: host spans of allowed URLs are protected in
      the replacement step and hidden from the survivor check.
- [x] 1.3 Tests for the three scenarios, through `ReversibleAnonymizer`; each
      checked once with its fix removed.

## 2. Out
- [ ] 2.1 Release, deploy (api and init-job on the same sha).
- [ ] 2.2 Reprocess the 90 documents that carry `www.[TOKEN]`; recount.
- [ ] 2.3 Close #157 with the numbers; archive.
