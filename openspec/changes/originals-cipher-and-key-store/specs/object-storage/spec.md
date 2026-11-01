## MODIFIED Requirements

### Requirement: Object store protocol and S3 driver

Document bytes SHALL be stored through an `ObjectStore` protocol (put/get/exists)
with an S3-compatible driver, so the backend is swappable. MinIO SHALL NOT be
used; SeaweedFS (PoC) and Ceph RGW (target) sit behind the S3 API.

#### Scenario: Stored bytes are retrievable by key

- **WHEN** unsealed bytes are put under a key and later fetched by that key
- **THEN** the identical bytes are returned

#### Scenario: A sealed object is refused by the plain read

- **WHEN** an object that carries the sealed header is fetched through the plain
  `get`
- **THEN** `SealedObjectError` is raised and no bytes are returned, so
  ciphertext is never handed back as if it were the original
