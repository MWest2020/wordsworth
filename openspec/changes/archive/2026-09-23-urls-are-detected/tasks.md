# Tasks

## 1. Corpus first
- [x] 1.1 `generate_ground_truth.py`: seed a party's website as `URL` gold
      (`www.` and `https://` forms, with and without a path).
- [x] 1.2 Seed a government URL as plain text: the counter-case that must not
      be found.
- [x] 1.3 Baseline: URL recall with the current lists (expected 0).

## 2. The lists
- [x] 2.1 `DetectionLists.apply`: deny matches go through the allow filter.
      Test first; it must fail against the current code.
- [x] 2.2 Before/after over every stored document: old and new `apply` agree
      on every type except `URL`.
- [x] 2.3 `deny.json`: the web-address rule, with its reason.
- [x] 2.4 `allow.json`: public hosts, each with a reason. National references,
      plus this installation's recurring institutions — chosen from the hosts
      that recur in the stored corpus, never from a single document.

## 3. Measured
- [x] 3.1 Evaluation corpus: URL recall, and zero false positives on the
      government counter-case.
- [x] 3.2 Stored corpus, read-only: how many URLs would become tokens, how many
      stay readable, and whether every single-document host is caught.

## 4. Out
- [x] 4.1 Release, deploy, reprocess the stored corpus. (151 documents; 150
      in the first Job, the deadlock victim afterwards on its own.)
- [x] 4.2 Recount on the stored corpus after reprocessing. (770 documents: 0
      whole readable URLs outside allow.json, 262 URL tokens in 119 documents,
      258 readable by exception; see meting-webadressen-06.md.)
- [x] 4.3 Close #124 with the numbers.
