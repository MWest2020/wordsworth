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
- [ ] 2.1 api: `replicas: 2`, required pod anti-affinity on
  `kubernetes.io/hostname`.
- [ ] 2.2 api: PodDisruptionBudget `minAvailable: 1`.
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
- [ ] 2.5 auth (oauth2-proxy): `replicas: 2`, anti-affinity, PDB. Sessions
  are the default cookie store signed with `OAUTH2_PROXY_COOKIE_SECRET` from
  one Secret, so either replica serves any user.
- [ ] 2.6 Proof in the cluster: delete one api pod while a probe hits the
  console continuously; no failed request. And an eviction of the last api
  pod is refused by the PDB.

## 3. The dependencies
- [ ] 3.1a OpenSearch with more than one node.
- [x] 3.1b Recorded *that* search drops out temporarily and what the console
  shows then: `docs/how-to/zoeken-valt-weg.md`. The distinction between "the
  index is unreachable" and "your query was refused" did not exist — both gave
  an exception's class name — and now lives in the seam
  (`search_index.SearchUnavailable`), not in the console. Only the read paths
  soften; ingest fails hard and holds the document back, because `indexed`
  without an index is a lie.
- [ ] 3.2 Ollama: a second instance, or a volume that can move.

## 4. Proof
- [ ] 4.1 A node-shutdown test: one node out, the console keeps answering,
  and the result is written down with the date and the node.
- [ ] 4.2 Only then may "highly available" appear in the documentation.

## 5. Cleanup
- [ ] 5.1 Inspect `wordsworth-corpus` (mounted by nothing, pinned to node-03)
  and delete it once its contents are shown to be unneeded.
