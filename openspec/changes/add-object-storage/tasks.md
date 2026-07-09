# Tasks — add-object-storage

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Object store seam
- [ ] 1.1 Add `boto3`; `object_store.py`: `ObjectStore` protocol + `S3ObjectStore`
      (S3-compatible endpoint/creds from config) + `InMemoryObjectStore`
- [ ] 1.2 Config: S3 endpoint, bucket, creds via SOPS+age/OpenBao (not hardcoded)
- [ ] 1.3 Tests: put/get round-trip; exists; in-memory double

## 2. Ingest + fetch wiring
- [ ] 2.1 Ingest stores PDF -> object_key; `process` fetches bytes by key
      (remove the direct-bytes shortcut), resume re-fetches deterministically
- [ ] 2.2 Tests: pipeline reads bytes from the store; missing key errors clearly

## 3. Integration
- [ ] 3.1 Integration test against a local SeaweedFS (skip if unavailable)
