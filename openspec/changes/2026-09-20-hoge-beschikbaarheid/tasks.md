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

    Third run 2026-09-26 16:55Z, with retries logged (#173, `7fe0e82`):
    `ollama-0` evicted, **302 of 302 queries answered**, and the probing pod
    logged exactly one retry -- `{"event": "retry", "what": "query_embed",
    "error": "EmbeddingUnavailable", "attempt": 1, "of": 3}`. One query that
    would have failed, answered on the other instance. That closes the
    inference: the retry fires, and it is what kept the count whole.

## Found on the way (2026-09-26)
- [x] `/ask` with a long context pushes Ollama past its 5 GiB limit. Two
  `/ask` calls (k=8, run while measuring 3.3.2) got **both** Ollama pods
  OOM-killed, exit 137, four minutes apart, so one instance served while the
  other restarted. The single instance before step 3 had the same limit.
  Not fixed: raise the limit (8.4-9.6 GiB is available per node) or bound the
  context, measured either way.

  Fixed 2026-09-28 (homelab `c03e91f`, limit 5Gi -> 7Gi; the measurement in
  `392043e`). Measured on `ollama-0` through wordsworth's own `rag.ask`
  (k=8), cgroup `memory.peak`: one call 6600 MiB, two concurrent 6693, two
  concurrent plus embeddings 6800; no restart. With both models loaded
  **anon memory is 5321 MiB** (`memory.stat`), above the old 5120 MiB: the
  OOM kills were certain, not unlucky. The other ~1.4 GiB is file cache from
  reading the models, reclaimable. Ollama's own log accounts for it:
  llama3.2 1918 MiB weights + 896 MiB KV (`n_ctx = 8192`, two parallel
  slots) + 424 MiB compute; bge-m3 1098 + 384 MiB. 7Gi is the limit the worst
  case ran under.
- [x] Two `/ask` calls on one instance take ~650 s each (one alone: 310 s),
  measured 2026-09-28, and the api gives generation 600 s
  (`WORDSWORTH_LLM_TIMEOUT` default). No longer an OOM, now a timeout. Also:
  all four measured answers came back ungrounded (0 citations). Neither is
  fixed.

  2026-09-28: Ollama set to one request per model at a time
  (`OLLAMA_NUM_PARALLEL=1`, homelab `649ba76`), measured on `ollama-0`: two
  concurrent `/ask` now take **234 s and 637 s** (was ~650 s each); one alone
  301 s. The first answer arrives almost three times sooner; the queued one
  still takes about as long and is still over the api's 600 s. Memory fell
  too: peak 6013 MiB (was 6600), anon 4527 (was 5321), llama KV cache 448 MiB
  (was 896). With two instances behind the Service, two concurrent calls land
  on different instances about half the time and both answer in ~300 s; on
  the same instance the second still times out through the api. Open.

  2026-09-29: `WORDSWORTH_LLM_TIMEOUT` 600 -> 900 s (homelab `90dc923`; the
  path in front of it allows it: gunicorn 1800 s, the tailnet proxies no
  response timeout). Measured end to end from a tailnet machine through
  `https://wordsworth-api.tail8f7877.ts.net`: two concurrent `/ask` (k=8),
  both confirmed on `ollama-0` from its request log, the worst case. **Both
  200, in 305 s and 546 s**, no restart. The queued call varies between runs
  (637 s on 09-28, 546 s here); 900 s covers both with room. Still open, and
  not a timeout: the grounding (see the 0-citation answers above).

## 3.3 The tailnet entry points (added 2026-09-26; design.md, Decision 6)
- [ ] 3.3 Both tailnet routes survive one node.
  - [x] 3.3.1 Verify how a `ProxyGroup` of `type: ingress` works on operator
    v1.102.2, and what it needs in the tailnet policy. Any policy change is
    Mark's; write it down before anything moves.

    Read from the operator source at tag v1.102.2 (2026-09-26):
    `ingress-for-pg.go` (Ingress) and `svc-for-pg.go` (LoadBalancer Service)
    both turn the resource into a **Tailscale Service** `svc:<hostname>`,
    created through the Tailscale API, tagged with the operator's default tags
    or the `tailscale.com/tags` annotation. The group's pods advertise it, and
    its addresses reach them "in the next netmap update if approved". A
    Tailscale Service that already exists without the operator's owner
    reference is an error, not a takeover.

    What that needs on the tailnet, all of it Mark's (tailnet admin):
    1. Tailscale Services available on the tailnet. A 2025-05 comment in the
       source says they were behind a per-tailnet alpha flag; whether that
       still holds could not be seen from here.
    2. The service approved for the operator's tag: an `autoApprovers`
       entry for `svc:wordsworth-api` (and `svc:wordsworth` if it stays) in
       the tailnet policy, or approval by hand in the admin console.
    3. HTTPS on the tailnet: already on (the current Ingress has a
       certificate).
  - [x] 3.3.2 Decide whether the http :8000 LoadBalancer (`wordsworth`) can go:
    check `wordsworthctl` and its callers against the https name.

    Checked 2026-09-26:
    - The CLI is documented and installed against the **raw tailnet IP**
      `http://100.100.181.23:8000` (`docs/reference/cli.md`,
      `scripts/install-cli.sh`), which is the :8000 LoadBalancer. In-cluster
      callers use the ClusterIP Service and are not affected.
    - **A Tailscale Service gets its own addresses** from the control plane,
      so moving either route onto a ProxyGroup changes the IP. Every CLI
      configured with `100.100.181.23` breaks either way. The name survives;
      the IP does not.
    - The https route's proxy (tailscaled serve, `ipn/ipnlocal/serve.go` at
      v1.102.2) sets no response timeout, only Go's default dial, TLS and
      idle timeouts, so a long ingest request is not cut off there. Read from
      source, not measured.

    Conclusion: the http LoadBalancer can go. Every CLI then points at
    `https://wordsworth-api.tail8f7877.ts.net`, a name rather than an IP, and
    the docs and installer say so. Where the CLI is configured outside this
    cluster (Mark's machines) is Mark's to change, one command:
    `wordsworth config --url https://wordsworth-api.tail8f7877.ts.net`.
  - [ ] 3.3.3 `ProxyGroup` type ingress, two replicas, a `ProxyClass`
    requiring different nodes.
  - [ ] 3.3.4 Move the remaining route(s) onto it, keeping their MagicDNS
    names; time the gap while a name passes from the old device to the
    group.
  - [ ] 3.3.5 Proof: probe each remaining name from a tailnet machine, five a
    second; evict one proxy pod; no failed request.

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
