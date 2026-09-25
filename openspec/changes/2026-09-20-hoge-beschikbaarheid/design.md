# Design: hoge-beschikbaarheid

Written 2026-09-25 for step 3 (tasks 3.1a and 3.2). Steps 1, 2 and 4 are
described in the proposal and tasks.

## What was measured

- **wordsworth is the only user of either service.** No other manifest in
  homelab, and no pod environment in the cluster, points at `opensearch` or
  `ollama`. Changing them touches nothing else.
- **OpenSearch** 2.19.1, one Deployment, `discovery.type: single-node`,
  security plugin off, heap 512 MB (56% used), 10 Gi `local-path` volume on
  node-02. The `wordsworth` index: 1 primary shard, `number_of_replicas: 1`,
  611 documents, 65 MB. That replica has nowhere to go, so the index is
  yellow today.
- **The embeddings exist only in the index.** Recomputing them took about
  eight hours on 2026-09-18. They are in `_source` (1024 floats per
  document), so copying documents copies them.
- **No `repository-s3` plugin** in the image, so a snapshot to SeaweedFS
  would first need an image change.
- **Ollama** 0.6.8, one Deployment, CPU only, 15 Gi `local-path` volume on
  node-03. Models are pulled by an ArgoCD PostSync Job **through the
  Service**, by floating tag: `bge-m3` (digest `79076464…2146bab`, 1.16 GB)
  and `llama3.2:3b` (`a80c4f17…cbb5b8b72`, 2.02 GB).
- **Memory actually available** (kubelet stats, 2026-09-25): node-01
  8.4 GiB, node-02 9.3 GiB, node-03 9.6 GiB. OpenSearch uses about 1.05 GiB,
  Ollama about 1.1 GiB idle and up to its 5 GiB limit with both models
  loaded.

## Decision 1 — neither needs shared storage

Both replicate above the disk. OpenSearch copies shards between its own nodes,
each on its own node-local volume; Ollama is stateless apart from its model
files, which every instance can hold its own copy of. So step 3 does not wait
for step 1, the same way step 2 did not. `local-path` stays.

The consequence to accept: a pod whose node is gone cannot move, because its
volume is on that node. It waits, Pending, until the node returns, while its
peers serve. That is the point of having peers.

## Decision 2 — OpenSearch: three nodes, not two

Three cluster-manager-eligible nodes, each also a data node, one per worker
node (required anti-affinity). With two, losing one leaves no majority to
elect a cluster manager, and the survivor stops accepting writes: two nodes
would be less available than one, not more.

- StatefulSet with a `volumeClaimTemplate` (10 Gi `local-path` each), a
  headless Service for discovery (`discovery.seed_hosts`), and
  `cluster.initial_cluster_manager_nodes` naming the three pods, for the
  first bootstrap only.
- Same heap and requests per node as today (512 MB, 1.5 Gi request): the
  index is 65 MB.
- `number_of_replicas: 1` on `wordsworth`, which it already has: two copies
  of every shard on two different nodes, so one node can go.
- PodDisruptionBudget `maxUnavailable: 1`.
- Still security plugin off, still ClusterIP. This is about availability,
  not about opening the service up.

## Decision 3 — OpenSearch migration: a new cluster beside the old, then switch

Converting the running single-node cluster in place is the step whose
failure costs the embeddings. So:

1. Stand up the three-node cluster under a **new** Service name next to the
   old one. The old Deployment keeps serving.
2. Copy the `wordsworth` index with **reindex-from-remote** (the old cluster
   in `reindex.remote.allowlist` on the new one). Document ids and `_source`,
   vectors included, come along. The index is created first with the current
   mapping, not left to be inferred.
3. Check before switching: the same document count, the same set of ids, and
   the vectors of a sample of documents equal, value for value.
4. Switch wordsworth's `WORDSWORTH_OPENSEARCH_URL` to the new Service.
5. Keep the old Deployment and its volume for a week as the rollback, then
   remove them.

The copy happens in a quiet window: no ingest, no reprocess Job running (the
same check the last three deploys needed). Anything indexed between copy and
switch would be missing, so the count check runs again after the switch.

Rejected: a snapshot to SeaweedFS, which needs a plugin and an image change
for a one-off copy of 65 MB. And adding nodes to the existing single-node
cluster, which is the path whose failure is the expensive one.

## Decision 4 — Ollama: two instances, each pulling its own models, pinned

- StatefulSet, two replicas, required anti-affinity, a 15 Gi `local-path`
  volume each, PodDisruptionBudget `maxUnavailable: 1`.
- **Each pod pulls its own models,** in an init container that starts a
  temporary server, pulls, and stops. The PostSync Job goes: through the
  Service it reaches one instance at random, and the other would start
  empty.
- **Pinned, and checked against the pin.** Two instances pulled at different
  times can hold different versions of `bge-m3`. Their vectors would then be
  mixed in one index, where kNN quietly compares numbers from two different
  models. The init container compares the pulled digest with the pinned one
  and fails the pod if they differ. A pod with the wrong model does not start;
  it does not serve slightly wrong vectors. The pins are today's digests,
  because those made every vector in the index now.
- The existing `ollama-models` volume is not reused: a StatefulSet names its
  own volumes. Each instance pulls about 3.2 GB once.
- **One change on the wordsworth side.** The Service balances requests, so
  an instance lost mid-request is an ordinary event. Today it fails the
  document: `EmbeddingError` wraps the transport error in a plain
  `Exception` with no status code and no "connection"/"timeout" in its name,
  so `retry.is_transient` says permanent. An embedding error caused by the
  transport (unreachable, timeout, 5xx) becomes transient, and bounded retry
  then reaches the other instance. An empty or malformed embedding stays
  permanent. This is not a fallback: after the retry budget the document
  still fails hard, as the architecture requires.

## Decision 5 — each gets its own proof, before step 4

Like step 2: evict one pod under a continuous probe, and the probe must not
fail.

- OpenSearch: `GET /search` through the api, five times a second; evict one
  OpenSearch pod; no failed search, and cluster health back to green after.
- Ollama: `GET /hybrid`, which needs a query embedding, under the same
  probe; evict one Ollama pod; no failed query. Known risk, stated before
  the test rather than explained after it: only ingest retries (3.2.1); a
  query embeds once. A query in flight on the evicted pod can fail. If the
  probe shows that, the query path gets one retry on a transport error, the
  same classification, before this counts as done.

This proves the services; it does not prove the node. With SeaweedFS still on
one node, a node-shutdown test (4.1) would still fail on node-01. That waits
for step 1.
