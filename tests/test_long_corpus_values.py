# SPDX-License-Identifier: MIT
"""Values that cannot be anyone's (synthetic-long-corpus)."""
import random

from wordsworth.detectors import is_valid_bsn, is_valid_iban
from wordsworth.eval.synthetic import bsn, bsn_test_range, iban, iban_fake_bank

_TEST_RANGE = range(999990000, 1000000000)


def test_bsn_test_range_is_in_the_logius_range_and_elfproef_valid():
    rng = random.Random(11)
    for _ in range(300):
        v = bsn_test_range(rng)
        assert is_valid_bsn(v)
        assert int(v) in _TEST_RANGE


def test_iban_fake_bank_is_mod97_valid_on_a_bank_code_nobody_has():
    rng = random.Random(12)
    for _ in range(300):
        v = iban_fake_bank(rng)
        assert is_valid_iban(v)
        assert v[4:8] == "ZZZZ"


def test_existing_bsn_and_iban_outputs_are_unchanged_for_a_fixed_seed():
    """The 500-document corpus (generate_ground_truth.py) must keep its
    values, so a measurement taken before this change stays comparable."""
    rng = random.Random(20260917)
    assert bsn(rng) == "924483027"
    assert iban(rng) == "NL78INGB9028901012"
