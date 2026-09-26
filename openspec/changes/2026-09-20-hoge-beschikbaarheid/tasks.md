# Tasks: hoge-beschikbaarheid

Rewritten 2026-09-23 after measuring the cluster again (see proposal). Step 2
no longer waits for step 1: the api mounts nothing tied to a node.

## 1. Object storage that survives a node (Mark's decision, homelab)
- [ ] 1.1 Choose object storage that survives one node, for the documents and
  for the WORM exports. A candidate counts only once Object Lock is shown to
  work on it.
- [ ] 1.2 Show it: a node goes away, objects stay readable and a
  retention-locked object stays locked.
- [ ] 1.3 Move the `wordsworth` bucket onto it.
- [ ] 1.4 Schedule both WORM exports (document chain and key-lifecycle
  stream). Parked until 1.1 by Mark, 2026-09-23.

## 2. The api and auth survive one node
- [x] 2.1 api: `replicas: 2`, required pod anti-affinity on
  `kubernetes.io/hostname`.
- [x] 2.2 api: PodDisruptionBudget `minAvailable: 1`.
- [x] 2.3 Rate-limit buckets shared by every replica: `rate_limit_pg`, in
  Postgres, wired in `serve.py`. Tests: two buckets over one database share
  the limit; 20 concurrent checks against a burst of 5 let exactly 5 through
  (a read-then-write version lets 20 through); the API key is stored hashed.
- [x] 2.4 Walk every write path for two writers at once, and list the result
  here.

  Walked 2026-09-23. "Two writers" is not new: sync endpoints already run in a
  threadpool, so one pod had concurrent writers before. Two replicas make the
  races likelier, not different.

  | Write path | Guard | Verdict |
  |---|---|---|
  | Document audit chain | advisory lock 4771 + UNIQUE `prev_hash` | safe |
  | Key-lifecycle stream | advisory lock 4772 + UNIQUE `prev_hash` | safe |
  | Data-key minting (`DurableKeyProvider`) | partial unique index on the active key per scope; the loser adopts the winner | safe |
  | Key cache per pod | `current_key` re-reads the active key every call; retired keys still resolve by id | safe |
  | Pseudonym mappings | was read-then-insert, loser's ingest failed on the PK | **fixed**: `INSERT … ON CONFLICT DO NOTHING`; both rows encrypt the same value |
  | `dossiers.ensure`, `roles.create` | savepoint around the insert | safe |
  | Summaries | `ON CONFLICT DO UPDATE` | safe |
  | Grants | random ids | safe |
  | Rate-limit buckets | were per process | **fixed** in 2.3 |
  | Document registration | read-then-insert on `object_key`, no unique constraint | **open**: the same bytes uploaded twice at once become two documents. Production already holds 791 documents over 618 distinct `object_key`s, so a unique index cannot simply be added. Needs its own change. |
- [x] 2.5 auth (oauth2-proxy): `replicas: 2`, anti-affinity, PDB. Sessions
  are the default cookie store signed with `OAUTH2_PROXY_COOKIE_SECRET` from
  one Secret, so either replica serves any user.
- [x] 2.6 Proof in the cluster: delete one api pod while a probe hits the
  console continuously; no failed request. And an eviction of the last api
  pod is refused by the PDB.

  Done 2026-09-23 on image `cbfa7a3d…` (main `4495e46`, homelab `9a338a0`).
  api on node-01 and node-02, auth on node-02 and node-03. Two probes hit
  `/health` five times a second for 100 s: the public route (tunnel → auth →
  api) and the tailnet route (straight to the api). Meanwhile, at 17:33:47Z,
  one api pod was evicted (201), a second eviction of the other api pod
  straight after was refused (`TooManyRequests: Cannot evict pod as it would
  violate the pod's disruption budget`), and one auth pod was evicted (201).
  Result: 302/302 public and 395/395 tailnet requests answered 200; the
  replacements came up on other nodes.

  Shared limit, live: three wrong keys to `/console/login` from inside each api
  pod to itself gave `[401, 401, 401]` on one and `[401, 401, 429]` on the
  other: five attempts in total, the configured burst, across two processes.

  Not proven by this: a node going away. Evicting a pod is gentler than losing
  its node, and SeaweedFS, OpenSearch and Ollama still each live on one node.
  That is step 4.

## 3. The dependencies
- [ ] 3.1a OpenSearch with more than one node. Plan: design.md, Decisions
  1–3 and 5.
  - [x] 3.1a.1 Three-node StatefulSet beside the old Deployment, under a new
    Service: one pod per worker node, headless discovery, PDB
    `maxUnavailable: 1`, same heap and requests per node.
  - [x] 3.1a.2 In a quiet window (no ingest, no reprocess Job): create
    `wordsworth` with the current mapping, reindex from remote, then compare
    count, id set, and a sample of vectors value for value.
  - [x] 3.1a.3 Switch `WORDSWORTH_OPENSEARCH_URL`; recount after the switch.
  - [x] 3.1a.4 Proof: evict one OpenSearch pod under a five-per-second
    `/search` probe; no failed search, health green again after.

    3.1a.1–3.1a.4 done 2026-09-26. Cluster up at 09:12Z (homelab
    `902e765`): green, one pod per worker node. In a quiet window (no Job, no
    audit record in ten minutes) the index was created from the old one's own
    settings and mapping and copied by reindex-from-remote: 611 created, no
    failures. Verified document by document: 611 = 611, none missing or
    extra, **no `_source` different**, vectors included; same mapping and
    analysis; green with the replica on a second node. Switched at 09:16Z
    (homelab `2f2b4d1`, a pod-template annotation rolls the api so `envFrom`
    picks the URL up) and verified again after: unchanged, no writes in
    between.

    BM25 ranks differently from before, 5 of 6 test queries (hybrid: 1 of 6,
    through its BM25 recall set). Not the copy: the old index still counted
    163 deleted documents in its statistics (field doc count 721 against 611
    live), left by the dedupe and by updates. The new one ranks over the
    corpus as it is.

    Proof: `/search` probe at three per second; the **cluster manager**
    `opensearch-cluster-1` evicted at 09:17:17Z, the second eviction refused by
    the PDB; **360 of 360 searches answered**; `opensearch-cluster-2` elected;
    green with three nodes again at 09:19:10Z.
  - [ ] 3.1a.5 After a week without rollback: remove the old Deployment and
    its volume. Due 2026-10-03.
- [x] 3.1b Recorded *that* search drops out temporarily and what the console
  shows then: `docs/how-to/zoeken-valt-weg.md`. The distinction between "the
  index is unreachable" and "your query was refused" did not exist — both gave
  an exception's class name — and now lives in the seam
  (`search_index.SearchUnavailable`), not in the console. Only the read paths
  soften; ingest fails hard and holds the document back, because `indexed`
  without an index is a lie.
- [x] 3.2 Ollama: a second instance. Plan: design.md, Decisions 1, 4 and 5.
  - [x] 3.2.1 wordsworth: an `EmbeddingError` caused by the transport is
    transient; an empty or malformed embedding stays permanent. Test both.
    `EmbeddingUnavailable` (unreachable, timeout, 5xx, cut-off response);
    `tests/test_embedding_transient.py`, including a document whose first
    embedding attempt hits a lost instance and is indexed on the retry.
    Checked both ways: without the classification 6 tests fail; with every
    failure made transient, 2 do.
  - [x] 3.2.2 Two-replica StatefulSet, required anti-affinity, PDB
    `maxUnavailable: 1`; each pod pulls its models in an init container and
    fails if a digest differs from the pin (`bge-m3` `79076464…2146bab`,
    `llama3.2:3b` `a80c4f17…cbb5b8b72`). The PostSync pull Job goes.
  - [x] 3.2.3 Check both instances report the pinned digests, and that the
    same text embeds to the same vector on each.

    Done 2026-09-26 (homelab `a9967f8`, then `712844b` removing the old
    Deployment and its volume). `ollama-0` on node-02, `ollama-1` on node-01;
    both init containers logged `bge-m3:latest = 790764642607 (pinned)` and
    `llama3.2:3b = a80c4f17acd5 (pinned)`. On three indexed documents, each
    instance embedded the indexed text to exactly the stored vector: cosine
    1.0, largest difference 0.0 over 1024 values. So both run the model that
    built the index, not merely a model with the same tag.
  - [x] 3.2.4 Proof: evict one Ollama pod under a five-per-second `/hybrid`
    probe; no failed query.

    First run 2026-09-26 08:45Z (three per second, under the rate limit):
    eviction of `ollama-0` 201, the second eviction refused by the PDB, the
    evicted pod back with the pinned models -- and 333 of 334 queries
    answered, one `500`: `connection refused`, the Service still routing to
    the pod being evicted. The risk named in design.md before the test. So
    `hybrid_search`, the one place every query embeds (`/hybrid`, console
    search, `/ask`), now takes the same bounded retry as ingest. The probe
    runs again after that deploy; this task closes on that run.

    Second run 2026-09-26 09:06Z, after the query retry was deployed
    (`e59bb3e`): `ollama-1` evicted (201), **327 of 327 queries answered**.
    `retry_transient` does not log, so this run cannot show whether a retry
    fired or the endpoint was simply not hit; the first run shows the failure
    happens, the unit test shows the retry covers it.

## 4. Proof
- [ ] 4.1 A node-shutdown test: one node out, the console keeps answering,
  and the result is written down with the date and the node.
- [ ] 4.2 Only then may "highly available" appear in the documentation.

## 5. Cleanup
- [x] 5.1 Inspect `wordsworth-corpus` (mounted by nothing, pinned to node-03)
  and delete it once its contents are shown to be unneeded.

  Inspected 2026-09-24 through a read-only pod: 204 files, 428 MB. 197 hash
  to a stored document's `object_key`. The other 6 PDFs are OCR-recovered
  scans, whose `object_key` moved to the OCR'd object (measurement 01,
  finding 2); the originals are in S3. `herkomst.jsonl` existed nowhere
  else and is now `docs/explanation/meting-woo-corpus-01.herkomst.jsonl`
  (same sha256, `24d67cce…`). The PVC was the staging area of batch intake
  between batches; `deploy/k8s/50-corpus.yaml` creates a fresh one as its
  first step, so the next batch is unaffected. Removed from homelab.
