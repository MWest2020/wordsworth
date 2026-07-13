# Tasks — add-object-storage

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Object store seam
- [x] 1.1 Add `boto3`; `object_store.py`: `ObjectStore` protocol + `S3ObjectStore`
      (S3-compatible endpoint/creds from config) + `InMemoryObjectStore`
- [x] 1.2 Config: S3 endpoint, bucket, creds via SOPS+age/OpenBao (not hardcoded)
- [x] 1.3 Tests: put/get round-trip; exists; in-memory double

## 2. Ingest + fetch wiring
- [ ] 2.1 Ingest puts PDF bytes and records the key (reuse the existing
      `object_key` column + `register`, don't add a second one); `process` takes
      an injected `ObjectStore` and fetches bytes by key (remove the direct-bytes
      shortcut); update the resume docstring; resume re-fetches deterministically
- [ ] 2.2 Tests: pipeline reads bytes from the store; a missing key raises (hard
      error, never empty bytes — no silent fallback)

## 3. Integration
- [x] 3.1 Integration test against a local SeaweedFS (skip if unavailable)
