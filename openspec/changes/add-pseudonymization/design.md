# Design decisions — add-pseudonymization

## Decision: mapping in a separated encrypted store (not in-document XMP)

The PoC-proven approach put AES-GCM ciphertext in the document's XMP metadata.
We deliberately choose a **separated encrypted store** instead. It wins on:

- **Export.** Documents *and* index can be shipped fully PII-free; the mapping
  never leaves with them.
- **Crypto-aging.** The mapping can be re-encrypted (key rotation, algorithm
  upgrade) without touching a single document.
- **Exfiltration risk.** A leaked document carries no ciphertext to attack; the
  mapping is a separate, separately-guarded asset.

Cost: one more store to run and back up. Acceptable — it is a PostgreSQL table.

## The two protocols (stubbed for the PoC)

```python
class KeyProvider(Protocol):
    def current_key(self) -> Key: ...          # {id, bytes}

class MappingStore(Protocol):
    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str) -> None: ...
    def get(self, pseudonym: str) -> Mapping | None: ...
```

- `StubKeyProvider`: key = sha256(passphrase), a single dev key. **Not for
  production** — no rotation/escrow. This is exactly the "stub behind a protocol"
  the scope calls for; the real lifecycle is MVP work.
- `PostgresMappingStore`: `pii_mappings(pseudonym PK, ciphertext, nonce, key_id,
  created_at)`. `put` is idempotent (a pseudonym maps to one ciphertext).

## Pseudonyms: stable, keyed, separate from the encryption key

Each value becomes `[TYPE:token]` where `token = HMAC(key, "TYPE:value")[:8]`.

- **Stable**: the same value yields the same pseudonym, so the index remains
  searchable/linkable on the pseudonym.
- **Keyed** (HMAC, not a bare hash): a low-entropy value like a BSN cannot be
  brute-forced back from the pseudonym.

**PoC limitation, documented:** the token is keyed with the KeyProvider key, so
key rotation would change tokens and break linking. The production design uses a
dedicated, separately-rotated pseudonymization secret. Stubbed here on purpose —
not a blocker for searchability.

## Deanonymization is audit-logged (never logs clear values)

`deanonymize(session, document_id, text, ...)` replaces pseudonyms with decrypted
originals and appends a `step="deanonymize"` record to the same append-only,
hash-chained audit trail. It is an access event, not a state transition, so it is
written via `audit.append` with `from_state == to_state` (current state). The
payload records the **pseudonyms and actor** — never the recovered clear values.

## Fit with the pipeline

`Pseudonymizer` implements the `Anonymizer` protocol, so it drops into
`process(..., anonymizer=pseudonymizer)` with no pipeline change. The PoC default
stays the irreversible `DeterministicAnonymizer`; pseudonymization is the
opt-in, reversible alternative. Same seam, different driver — that is the point.
