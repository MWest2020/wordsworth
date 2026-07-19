# Design decisions — add-object-storage

## Seam

```python
class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
```

- `S3ObjectStore`: boto3 client against any S3-compatible endpoint (SeaweedFS PoC,
  Ceph RGW target). Endpoint/creds from config, sourced via SOPS+age or OpenBao.
- `InMemoryObjectStore`: dict-backed test double — the pipeline never depends on a
  live bucket in tests.

## Ingest and fetch

Ingest: `put` the PDF under a content-addressed or uuid key, record it as the
document's `object_key`. `process(document_id, ...)` fetches bytes via
`store.get(object_key)` rather than receiving `pdf_bytes` directly — closing the
PoC shortcut. Resume/re-processing re-fetches deterministically by key.

## Sovereignty (invariants)

- **No MinIO** (open-source edition deprecated April 2026). SeaweedFS (Apache-2.0)
  for the PoC; Ceph RGW as the production/shared target. The S3 API is the
  contract, so the backend is a config change.
- Secrets via **SOPS+age or OpenBao** only — never hardcoded, client-side, or
  commercial.

## Not in scope

Bucket lifecycle policies, multipart tuning, cross-region. Object Lock/WORM for
the audit export lives in `add-audit-worm-export`.
