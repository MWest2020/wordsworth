## Why

The PoC passes PDF bytes to the pipeline directly; there is no object-storage
adapter yet. Production ingests documents into S3-compatible object storage and
the pipeline fetches them by key. MinIO is banned (deprecated); SeaweedFS is the
PoC backend, Ceph RGW the sovereign target — both behind the S3 seam.

## What Changes

- Introduce an **`ObjectStore` protocol** (put / get / exists) with an **S3
  driver** (boto3, any S3-compatible endpoint) and an in-memory test double.
- **Ingest stores** the PDF and records its object key; **`process` fetches** the
  bytes by key instead of receiving them directly (removes the PoC shortcut).
- Credentials/endpoint come from SOPS+age or OpenBao — never hardcoded, never
  client-side, never commercial.

## Capabilities

### New Capabilities
- `object-storage`: the S3-compatible object store seam, ingest storage, and
  pipeline fetch-by-key.

## Impact

- New dependency: `boto3` (S3 client). No MinIO. SeaweedFS (PoC) / Ceph RGW
  (target) behind the same S3 API.
- `register`/ingest stores bytes → key; `process` fetches by key. Does not touch
  `CLAUDE.md`, `.claude/agents/`, CI.
