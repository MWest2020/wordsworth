# Design

## The shared interface is operations, not `KeyProvider` / `MappingStore`

`KeyProvider.key(key_id) -> Key(material)` and `MappingStore.get(token)` hand
key material and ciphertext to the caller. A service driver cannot implement
them: it must never return either (`key-service-pseudonymise`, "Only reveal
returns a clear value"). So neither is the shared interface; they stay what
the in-process driver uses internally.

The interface is one level up, at the operations the service already exposes:

- `pseudonymise(document_id, domain, items[type, value]) -> tokens`
- `open_original(document_id, purpose) -> plaintext` (subject to the
  open-limits rate limit)
- `delete_document(document_id)`

Reveal (`decide`, `reveal`) is not in it; its switch waits for #524. Names and
signatures beyond these operations are fixed in the build.

Rejected: widening `KeyProvider` and `MappingStore` with service methods (a
driver that raises on half its interface is a fallback in disguise); one
interface including reveal now (it pulls the open question into the seam).

## Configuration: in-process by default, unknown refuses

The driver is chosen by configuration. Unset builds the in-process driver, so
the seam deploys with no change in behaviour. An unknown value refuses to
start rather than falling back (no silent fallbacks).

## Contract tests, one module, both drivers

The same test module is parametrised over both drivers. The service driver
runs against the service in-process in the test (as the service's own tests
do). Same results is the claim; the tests are the evidence.

## The pin: tokens depend on the vault

The service imports `Pseudonymizer` and `DurableKeyProvider` from wordsworth,
so a token is the same through either only if the service sees the same keys.
The pin test copies a vault into a service database as a fixture (not the
migration, which is the switch's), checks equal tokens, then changes one key's
material and checks the token differs. Rejected: a second token implementation
in the service (two functions that must agree forever).

## Maintenance mode lives here, because the switch needs it

The migration copies state and verifies it; ingest and grant changes during
the copy would make the copy inconsistent. So there is a mode in which those
writes are refused with a retryable answer that names maintenance, while
search and the console keep working. It lives in the seam so it is built and
tested before anything depends on it. Rejected: stopping the process (search
and the console would go down with it); locking tables (a long lock that hides
the reason from callers).

## The roadmap

The roadmap lists key-service parts 2a to 3 as open although their changes are
merged and archived, and one item, "wordsworth cut over to the key service",
for what is now three builds. The fix corrects both; an item is done only with
evidence.
