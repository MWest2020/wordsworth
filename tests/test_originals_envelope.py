# SPDX-License-Identifier: MIT
"""The sealed-object format (task 1): round trip, header shape, and fail-closed
on every tamper the design names (originals-cipher-and-key-store)."""
import os

import pytest

from wordsworth.originals_envelope import HEADER_LEN, HEADER_MAGIC, open as envelope_open, seal

DEK = os.urandom(32)
OTHER_DEK = os.urandom(32)
MARKER = b"TOTALLY-SECRET-PLAINTEXT-MARKER"
PLAINTEXT = b"%PDF-1.4 " + MARKER + b" rest of the document"


def test_round_trip():
    sealed = seal(DEK, "a" * 12, "documents/x", PLAINTEXT)
    assert envelope_open(DEK, "a" * 12, "documents/x", sealed) == PLAINTEXT


def test_sealed_bytes_start_with_header_and_hide_the_plaintext():
    sealed = seal(DEK, "a" * 12, "documents/x", PLAINTEXT)
    assert sealed[:len(HEADER_MAGIC)] == HEADER_MAGIC
    assert len(sealed) >= HEADER_LEN
    assert MARKER not in sealed


def test_flipped_ciphertext_byte_fails_closed():
    sealed = bytearray(seal(DEK, "a" * 12, "documents/x", PLAINTEXT))
    sealed[HEADER_LEN] ^= 0x01  # first byte of the ciphertext
    with pytest.raises(Exception):
        envelope_open(DEK, "a" * 12, "documents/x", bytes(sealed))


def test_flipped_tag_byte_fails_closed():
    sealed = bytearray(seal(DEK, "a" * 12, "documents/x", PLAINTEXT))
    sealed[-1] ^= 0x01  # last byte of the GCM tag
    with pytest.raises(Exception):
        envelope_open(DEK, "a" * 12, "documents/x", bytes(sealed))


def test_changed_header_key_id_fails_closed():
    sealed = seal(DEK, "a" * 12, "documents/x", PLAINTEXT)
    with pytest.raises(Exception):
        envelope_open(DEK, "b" * 12, "documents/x", sealed)


def test_copied_to_another_object_key_fails_closed():
    sealed = seal(DEK, "a" * 12, "documents/x", PLAINTEXT)
    with pytest.raises(Exception):
        envelope_open(DEK, "a" * 12, "documents/y", sealed)


def test_two_sealed_objects_swapped_fail_closed():
    sealed_x = seal(DEK, "a" * 12, "documents/x", PLAINTEXT)
    sealed_y = seal(OTHER_DEK, "b" * 12, "documents/y", b"different doc")
    with pytest.raises(Exception):
        envelope_open(DEK, "a" * 12, "documents/x", sealed_y)
    with pytest.raises(Exception):
        envelope_open(OTHER_DEK, "b" * 12, "documents/y", sealed_x)


def test_no_plaintext_leaks_through_the_exception():
    sealed = bytearray(seal(DEK, "a" * 12, "documents/x", PLAINTEXT))
    sealed[HEADER_LEN] ^= 0x01
    try:
        envelope_open(DEK, "a" * 12, "documents/x", bytes(sealed))
    except Exception as exc:
        assert MARKER not in str(exc).encode("utf-8", "ignore")
    else:
        pytest.fail("expected open() to raise")
