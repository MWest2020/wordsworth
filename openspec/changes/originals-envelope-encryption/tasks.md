# Tasks

## 1. Sealing new originals
- [ ] `EncryptingObjectStore` + `DocumentKeys` behind the `ObjectStore` seam;
      ingest stores originals sealed. Proved by: a round-trip test (put, get,
      bytes equal) against FakeTransit.
- [ ] The stored object contains no plaintext. Proved by: a test that the raw
      bytes in the inner store don't contain a known marker string from the
      PDF and start with the header.
- [ ] Tampering is refused: a flipped ciphertext byte, a swapped header
      `key_id`, and an object copied to another document's id each fail with
      an error and no plaintext. Proved by: three negative tests.
- [ ] A wrong or unavailable KEK fails closed (no plaintext, no fallback to the
      legacy path for a sealed object). Proved by: a test with a FakeTransit
      under another KEK and one that raises.
- [ ] Legacy plaintext objects are still read; nothing is ever written in
      clear. Proved by: a test with a header-less object, and one asserting
      `put_original` never writes without the header.
- [ ] De-duplication by plaintext hash still works. Proved by: a test that the
      same bytes ingested twice yield one object key and one data key.
- [ ] Clear key material never reaches logs or exceptions. Proved by: a test
      capturing logs during seal/open/failure and asserting the DEK bytes (hex
      and base64) are absent.
## 2. Configuration
- [ ] KEK name and OpenBao address per domain, defaulting to the current KEK.
      Proved by: a config test; docs.
## 3. Docs
- [ ] `docs/reference/architecture.md` (storage section) and a how-to
      `docs/how-to/originals-encryption.md` (what is encrypted, where the keys
      are, what a sealed OpenBao means). ADR-0008 linked.
