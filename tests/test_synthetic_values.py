# SPDX-License-Identifier: MIT
"""Values added for the long corpus (synthetic-long-corpus): a BSN in the
published Logius test range, and an IBAN on a bank code nobody holds."""
import random

from wordsworth.detectors import is_valid_bsn, is_valid_iban
from wordsworth.eval.synthetic import bsn, bsn_test_range, iban, iban_fake_bank


def test_bsn_test_range_is_in_the_published_range_and_valid():
    rng = random.Random(7)
    values = [bsn_test_range(rng) for _ in range(300)]
    assert all(is_valid_bsn(v) for v in values)
    assert all(999990000 <= int(v) <= 999999999 for v in values)


def test_iban_fake_bank_is_on_bank_code_zzzz_and_valid():
    rng = random.Random(7)
    values = [iban_fake_bank(rng) for _ in range(300)]
    assert all(is_valid_iban(v) for v in values)
    assert all(v[4:8] == "ZZZZ" for v in values)


def test_bsn_and_iban_outputs_are_unchanged_for_a_fixed_seed():
    """The 500-document corpus must keep its values: adding bsn_test_range
    and iban_fake_bank next to bsn/iban must not alter what the existing two
    draw for the same seed."""
    rng = random.Random(42)
    assert [bsn(rng) for _ in range(5)] == [
        "104332189", "794026540", "235116154", "594078167", "184959317"]
    rng = random.Random(42)
    assert [iban(rng) for _ in range(5)] == [
        "NL23INGB3746317213", "NL52INGB9697354961", "NL37INGB2181241943",
        "NL73INGB1958682846", "NL46INGB4163119785"]
