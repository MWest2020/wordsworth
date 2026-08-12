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

Wordsworth has no CI docker-build workflow yet; build on the factory and push to
GHCR (mirrors OpenAnonymiser's GHCR pattern). The image is light (no torch).

```
# from the repo root
docker build -f deploy/Dockerfile -t ghcr.io/mwest2020/wordsworth:latest .
echo "$GITHUB_TOKEN" | docker login ghcr.io -u <gh-user> --password-stdin
docker push ghcr.io/mwest2020/wordsworth:latest
```

(A `.github/workflows/docker-build.yml` with a Trivy gate can be added later,
mirroring `OpenAnonymiser_light/.github/workflows/docker-build.yml`.)

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
kubectl apply -f k8s/30-api.yaml             # API Deployment + Service
kubectl -n wordsworth rollout status deploy/wordsworth-api
```

Smoke the API:

```
kubectl -n wordsworth port-forward svc/wordsworth-api 8000:8000
curl -s localhost:8000/health
```

## 4. Ingest a corpus

Make the PDFs available at `/corpus` (the template mounts a PVC
`wordsworth-corpus`; adjust to your source), then:

```
kubectl apply -f k8s/40-ingest-job.yaml
kubectl -n wordsworth logs -f job/wordsworth-ingest
```

Each document prints its terminal state; the job exits 0 only if **all** reached
`indexed`. A failure is loud (no clear text is stored or indexed).

## Hardening follow-ups (alma decisions)

- **Transport of pre-anonymization PII.** The ingest job POSTs raw text (still
  containing PII) to the OpenAnonymiser service over in-cluster `http://`. This is
  the one hop where clear PII crosses the pod network unencrypted — acceptable
  under the sovereign in-cluster model, but consider mesh mTLS or `https` on the
  service (set `WORDSWORTH_OPENANONYMISER_URL` to `https://...`; httpx verifies
  by default).
- **Image pinning.** Manifests use `:latest` and the Dockerfile uses tag-pinned
  bases. For reproducibility/supply-chain, pin by digest and add a Trivy-gated CI
  build (mirror `OpenAnonymiser_light/.github/workflows/docker-build.yml`).

## Invariants (do not break)

- No clear PII to the index; anonymize failure (incl. the OpenAnonymiser service
  being down) is a hard error.
- Append-only, hash-chained audit in PostgreSQL.
- No cloud APIs in the critical path — the OpenAnonymiser service is self-hosted
  (sovereign), reached in-cluster.
- Secrets only via the environment (SOPS+age / OpenBao); never in the image, the
  manifests, or logs.
