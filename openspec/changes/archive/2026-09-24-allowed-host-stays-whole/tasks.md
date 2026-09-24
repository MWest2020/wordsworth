# Tasks: allowed-host-stays-whole

## 1. Code
- [x] 1.1 `DetectionLists.allowed_spans(text, type)`: the spans `apply`
      suppresses, one definition.
- [x] 1.2 `ReversibleAnonymizer`: host spans of allowed URLs are protected in
      the replacement step and hidden from the survivor check.
- [x] 1.3 Tests for the three scenarios, through `ReversibleAnonymizer`; each
      checked once with its fix removed.

## 2. Out
- [x] 2.1 Release, deploy (api and init-job on the same sha). (68203ee, rolled
      out together with the Origin fix.)
- [x] 2.2 Reprocess the 90 documents that carry `www.[TOKEN]`; recount.
      (90/90 after the OpenBao token was reissued; `www.[TOKEN]` 133 -> 1,
      readable by exception 258 -> 412, whole readable outside allow.json 0.)
- [x] 2.3 Close #157 with the numbers; archive.
