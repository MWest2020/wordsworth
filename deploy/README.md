# Deploying wordsworth on alma

A runbook, not an introduction. What wordsworth **is** and how its parts relate
is the [README](../README.md); this page is how to run it here.

## What runs where

One cluster, two namespaces, human-operated.

```
  namespace: wordsworth                     namespace: openanonymiser
  ┌────────────────────────────────┐        ┌──────────────────────────┐
  │ wordsworth-init      (Job)     │        │ OpenAnonymiser (GLiNER)  │
  │ wordsworth-ingest    (Job)  ───┼───────▶│ HTTP, entity PII         │
  │ wordsworth-api       (Deploy)  │        └──────────────────────────┘
  └────────────────────────────────┘
        │        │        │        │
        ▼        ▼        ▼        ▼
       S3   PostgreSQL  OpenSearch  Ollama
```

The homelab cluster is lab and factory (build, CI, validation); the real
workload runs on **alma**. Claude is read-only on alma — every deploy step below
is a human action.

## Prerequisites on alma

Provisioned and reachable in-cluster (set their DNS in `k8s/10-config.yaml`):

- **PostgreSQL** — a `wordsworth` database + a role allowed to create functions
  and triggers (for the append-only audit trigger).
- **OpenSearch** — reachable; the index is created by the pipeline.
- **Ollama** — with the `bge-m3` embedding model pulled (and `llama3.1` if `/ask`
  is used).
- **S3-compatible object store** — a `wordsworth` bucket + access/secret keys.
- **OpenAnonymiser GLiNER service** — deploy from the OpenAnonymiser repo first
  (`deploy/alma-deployment.yaml`); Wordsworth expects it at
  `http://openanonymiser.openanonymiser.svc.cluster.local:8080`.

Read-only survey of what alma already runs (run these yourself):

```
kubectl get ns
kubectl get svc -A | grep -Ei 'postgres|opensearch|ollama|s3|seaweed|ceph|minio|anonymiser'
kubectl get storageclass
kubectl get ingressclass
```

Feed the results back to tune `10-config.yaml` (service DNS), `40-ingest-job.yaml`
(corpus PVC + storageClass), and the Ingress block in `30-api.yaml`.

## 1. Build + push the image (factory)

CI builds and pushes automatically: `.github/workflows/docker-build.yml` runs a
fast test gate → builds `deploy/Dockerfile` → Trivy-scans (HIGH/CRITICAL,
ignore-unfixed) → pushes to GHCR on every push to `main`, tagging `:latest`,
`:main`, and `:sha-<short>` (auth via the built-in `GITHUB_TOKEN`). PRs build +
scan without pushing. Trigger a specific ref manually with
`gh workflow run "Build and Push Docker Image" -f ref=main`.

Local build (fallback; the image is light — no torch):

```
docker build -f deploy/Dockerfile -t ghcr.io/mwest2020/wordsworth:latest .
echo "$GITHUB_TOKEN" | docker login ghcr.io -u <gh-user> --password-stdin
docker push ghcr.io/mwest2020/wordsworth:latest
```

## 2. Configure

Edit `k8s/10-config.yaml`: replace every `<...>` with alma's service DNS. Do
**not** commit real secret values — supply `wordsworth-secrets` via SOPS+age or
OpenBao. The `Secret` in the file is a shape template only.

## 3. Deploy

```
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/10-config.yaml          # or your SOPS/OpenBao-managed equivalent
kubectl apply -f k8s/20-init-job.yaml        # one-shot schema bootstrap (idempotent)
kubectl -n wordsworth wait --for=condition=complete job/wordsworth-init --timeout=120s
kubectl apply -f k8s/30-api.yaml             # API Deployment + Service (ClusterIP)
kubectl -n wordsworth rollout status deploy/wordsworth-api
```

Smoke the API in-cluster:

```
kubectl -n wordsworth port-forward svc/wordsworth-api 8000:8000
curl -s localhost:8000/health
```

## 4. Expose the API on the tailnet (durable, Tailscale-only)

Make the API reachable from any machine on the tailnet — not public — via the
Tailscale k8s operator:

```
kubectl apply -f k8s/60-api-tailscale.yaml
kubectl -n wordsworth get svc wordsworth-api-ts -o wide   # shows the tailnet name/IP
# from any tailnet machine:
curl -s http://wordsworth.<tailnet>.ts.net:8000/health
```

Requires the Tailscale operator on alma; see the header of
`60-api-tailscale.yaml` for the `tailscale serve` fallback. This stays open
within Tailscale (kept, not torn down).

## 5. Load the corpus into a PVC

```
kubectl apply -f k8s/50-corpus.yaml                       # PVC + loader pod
kubectl -n wordsworth cp ./corpus/. wordsworth-corpus-loader:/corpus/
kubectl -n wordsworth delete pod wordsworth-corpus-loader # free the RWO PVC
```

(Or rsync onto a node and adjust the PVC/volume source.) Size the PVC in
`50-corpus.yaml` to the corpus.

**Where a corpus comes from:** `scripts/eval/fetch_woo_corpus.py` pulls published
Woo documents (see `scripts/eval/README.md` for which sources allow it and which
do not). Run 2026-09-13: 200 PDFs, 428 MB, no errors.

**Getting 400 MB through `kubectl cp` from a workstation** is slow and dies on a
broken connection. What worked: tar it, `scp` to the jump host, unpack there, and
`kubectl cp` from a machine that sits next to the cluster.

```
tar czf corpus.tgz -C ./corpus . && scp corpus.tgz jump:/tmp/
ssh jump 'mkdir -p /tmp/c && tar xzf /tmp/corpus.tgz -C /tmp/c \
  && cd /tmp/c && kubectl -n wordsworth cp . wordsworth-corpus-loader:/corpus/'
```

## 6. Ingest a corpus

```
kubectl apply -f k8s/40-ingest-job.yaml
kubectl -n wordsworth logs -f job/wordsworth-ingest
```

**If the pod never starts and `logs` says nothing**, look at `describe` — not at
the logs. A wrong `secretRef` leaves the pod in `CreateContainerConfigError`, and
in that state there is no container and therefore no log output at all:

```
kubectl -n wordsworth describe pod -l job=ingest | tail -5
#   Error: secret "wordsworth-secrets" not found
```

The secret names in `40-ingest-job.yaml` must match **your** deployment. The
template in `10-config.yaml` uses one combined `wordsworth-secrets`; the
deployment in `MWest2020/homelab` splits it into `wordsworth-db`,
`wordsworth-s3`, `wordsworth-openbao` and `wordsworth-apikeys`. The Job now names
those four, because that is what actually runs.

Each document prints its terminal state; the job exits 0 only if **all** reached
`indexed`. A failure is loud (no clear text is stored or indexed). Then validate
functionally over the tailnet API (`/search`, `/hybrid`, `/ask`) — confirm no
clear PII appears in results.

## 7. Re-index an existing corpus

After a detector change, the documents already in the index still carry the old
de-identification. `/reprocess` re-runs the de-identify step over every `indexed`
document with the **current** code.

```
kubectl -n wordsworth apply -f k8s/45-reprocess-job.yaml
kubectl -n wordsworth logs -f job/wordsworth-reprocess
```

**Run it as a Job, never through `kubectl exec`.** Measured 2026-09-13: an
`exec`-driven run lost its websocket after four hours —

    "Copying stdout failed" err="websocket: close 1006 (abnormal closure)"

The *work* carried on (the HTTP call runs inside the api pod), but the client
that would read the result was gone, so the endpoint's outcome was lost for good
and progress could only be read from the audit table. A run of hours does not
belong on an interactive connection.

Expect roughly two minutes per document: every one goes through GLiNER and
bge-m3 again. Progress while it runs:

```
kubectl -n wordsworth exec deploy/wordsworth-api -- python3 -c "
import os; from sqlalchemy import create_engine, text
e=create_engine(os.environ['WORDSWORTH_DATABASE_URL'])
with e.connect() as c:
    print(c.execute(text(\"select count(*) from audit_records where step='reanonymize'\")).scalar())"
```

Note that `/reprocess` writes through the **reversible** pseudonymizer: a corpus
first indexed with the irreversible anonymizer changes placeholder shape from
`<PERSON>` to `[PERSON:hash8]`. That is the documented purpose of the endpoint —
less is exposed, not more, since the value moves into the encrypted mapping store
instead of being discarded.

## Hardening follow-ups (alma decisions)

- **Transport of pre-anonymization PII — decided, see
  [ADR-0006](../docs/explanation/adr/0006-clear-pii-over-the-in-cluster-hop.md).**
  The ingest POSTs raw text (still containing PII) to OpenAnonymiser over
  in-cluster `http://`. Accepted for a single-tenant cluster, **with a condition**:
  the moment this cluster carries a second tenant, or any workload not operated by
  the same party, it becomes a blocker. The step then is `https://` on the service,
  not a mesh.
- **Image pinning — done for our own images (2026-09-13).** The manifests pin by
  `@sha256:` digest and `scripts/pin_check.py` enforces it in CI. A tag is not a
  pin: `:latest` obviously moves, and `sha-<commit>` moves too, because nothing
  stops a re-push of that tag to different bytes. For a system that processes
  personal data, "which code has seen this document" is an audit question.
  The templates carry the placeholder `@sha256:<digest>` on purpose — a template
  must not ship somebody else's digest. Fill it in with:

      gh api user/packages/container/wordsworth/versions \
        --jq '.[] | select(.metadata.container.tags[]? == "sha-<commit>") | .name'

  **Still open:** the Dockerfile's base images use tag pins, and `busybox` in the
  corpus loader is not pinned at all — deliberately, it is a throwaway helper
  that touches nothing in the straat.

## Invariants (do not break)

- No clear PII to the index; anonymize failure (incl. the OpenAnonymiser service
  being down) is a hard error.
- Append-only, hash-chained audit in PostgreSQL.
- No cloud APIs in the critical path — the OpenAnonymiser service is self-hosted
  (sovereign), reached in-cluster.
- Secrets only via the environment (SOPS+age / OpenBao); never in the image, the
  manifests, or logs.
