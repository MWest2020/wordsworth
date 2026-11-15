# SPDX-License-Identifier: MIT
"""The object-storage seam's errors and its sealed-header check, in a module of
their own so that both `object_store` (the protocol, the in-memory double) and
`object_store_s3` (the S3 driver) import them without importing each other.
Import them from `wordsworth.object_store`, which re-exports them."""
from __future__ import annotations

#: The sealed-object header's magic bytes (originals_envelope.HEADER_MAGIC),
#: duplicated here on purpose: this is the lower layer, and it must never
#: import originals_envelope to find out whether an object is sealed.
_SEALED_MAGIC = b"WWENC"


class ObjectStoreError(Exception):
    """Raised when an object cannot be stored or fetched (e.g. a missing key)."""


class ObjectMissingError(ObjectStoreError):
    """The store answered, and the object is not there. Every other read error
    (a broken connection, a timeout, a 5xx) is a plain ObjectStoreError: the
    object may well exist, and a report must never call it missing."""


class SealedObjectError(ObjectStoreError):
    """Raised by the plain `get` when the object carries the sealed header:
    ciphertext must never be handed back to a caller expecting a PDF."""


def _is_sealed(data: bytes) -> bool:
    return data[:len(_SEALED_MAGIC)] == _SEALED_MAGIC
