## ADDED Requirements

### Requirement: Object store protocol and S3 driver

Document bytes SHALL be stored through an `ObjectStore` protocol (put/get/exists)
with an S3-compatible driver, so the backend is swappable. MinIO SHALL NOT be
used; SeaweedFS (PoC) and Ceph RGW (target) sit behind the S3 API.

#### Scenario: Stored bytes are retrievable by key

- **WHEN** bytes are put under a key and later fetched by that key
- **THEN** the identical bytes are returned

### Requirement: Ingest stores, pipeline fetches by key

Ingest SHALL store the document bytes and record the object key; the pipeline
SHALL fetch the bytes by key rather than receiving them directly.

#### Scenario: Pipeline reads from the object store

- **WHEN** a document is processed
- **THEN** its bytes are fetched from the object store by its recorded key

### Requirement: Sovereign credentials

Endpoint and credentials SHALL come from SOPS+age or OpenBao — never hardcoded,
client-side, or commercially licensed.

#### Scenario: No hardcoded credentials

- **WHEN** the S3 driver is configured
- **THEN** its credentials are read from the secret source, not from source code
