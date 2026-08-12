# Wordsworth — deploy (alma)

Run the full Wordsworth straat on real corpora on **alma** (production). The
homelab cluster is lab + factory (build/CI/validate); the real workload runs on
alma. Claude is read-only on alma — every deploy step here is a human action.

## Architecture

```
                         ┌────────────────────────────────────────────┐
  PDF corpus ──▶ wordsworth-ingest (Job)                               │
                    │  ingest → OCR recovery → anonymize → store → index│
                    │                        │                          │
                    │                        ▼                          │
                    │        OpenAnonymiser GLiNER service (HTTP) ◀──────┘
                    ▼                        (namespace: openanonymiser)
   S3 (object store) · PostgreSQL (audit + state) · OpenSearch (index) · Ollama (bge-m3)
                    ▲
  wordsworth-api (Deployment) ── read surface: state / metrics / search / hybrid / ask
```

- **Anonymize (Architecture A):** Wordsworth runs its deterministic regex pass
  (BSN/IBAN/email) in-process, then calls the **OpenAnonymiser GLiNER service**
  over HTTP for entity PII (names). No torch/spaCy/GLiNER in Wordsworth itself.
  Service down/unreachable ⇒ hard failure, never un-redacted pass-through.
- One image, three entrypoints: `uvicorn wordsworth.serve:app` (API, default
  CMD), `wordsworth-init` (schema), `wordsworth-ingest` (corpus straat).

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

## 6. Ingest a corpus

```
kubectl apply -f k8s/40-ingest-job.yaml
kubectl -n wordsworth logs -f job/wordsworth-ingest
```

Each document prints its terminal state; the job exits 0 only if **all** reached
`indexed`. A failure is loud (no clear text is stored or indexed). Then validate
functionally over the tailnet API (`/search`, `/hybrid`, `/ask`) — confirm no
clear PII appears in results.

## Hardening follow-ups (alma decisions)

- **Transport of pre-anonymization PII.** The ingest job POSTs raw text (still
  containing PII) to the OpenAnonymiser service over in-cluster `http://`. This is
  the one hop where clear PII crosses the pod network unencrypted — acceptable
  under the sovereign in-cluster model, but consider mesh mTLS or `https` on the
  service (set `WORDSWORTH_OPENANONYMISER_URL` to `https://...`; httpx verifies
  by default).
- **Image pinning.** The CI build (`docker-build.yml`) already Trivy-scans every
  image. Remaining: manifests use `:latest` and the Dockerfile uses tag-pinned
  bases — for full reproducibility/supply-chain, pin by digest.

## Invariants (do not break)

- No clear PII to the index; anonymize failure (incl. the OpenAnonymiser service
  being down) is a hard error.
- Append-only, hash-chained audit in PostgreSQL.
- No cloud APIs in the critical path — the OpenAnonymiser service is self-hosted
  (sovereign), reached in-cluster.
- Secrets only via the environment (SOPS+age / OpenBao); never in the image, the
  manifests, or logs.
