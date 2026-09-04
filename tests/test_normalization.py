"""add-value-normalisation: typed normalisation feeds the HMAC; the stored
value stays the original; the profile version is recorded per mapping."""
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.normalization import PROFILE_VERSION, normalize
from wordsworth.pseudonymizer import Pseudonymizer, _reveal, _token

KEY = b"k" * 32


def test_default_is_trim_and_nfc():
    # "é" as e + combining acute (NFD) normalises to the single NFC code point.
    assert normalize("UNKNOWN_TYPE", "  café  ") == "café"


def test_bsn_strips_separators_and_pads():
    assert normalize("bsn", "1234.56.789") == "123456789"
    assert normalize("BSN", "12345678") == "012345678"
    assert normalize("BSN", "1234 5678 9") == "123456789"


def test_bsn_non_digits_fall_back_to_default():
    assert normalize("BSN", " abc ") == "abc"


def test_names_and_locations_casefold():
    assert normalize("PERSON", "Jansen") == normalize("person", " jansen ")
    assert normalize("LOCATION", "Haarlem") == "haarlem"
    assert normalize("EMAIL", "Jan.Jansen@Haarlem.nl") == "jan.jansen@haarlem.nl"


def test_postcode_strips_space_uppercases():
    assert normalize("POSTCODE", "2011 ab") == "2011AB"


def test_dates_become_iso_8601_when_parseable():
    assert normalize("DATE", "01-02-1990") == "1990-02-01"
    assert normalize("DATE_TIME", "1990-02-01") == "1990-02-01"
    assert normalize("DATE", "gisteren") == "gisteren"  # unparseable: stable, no raise


def test_token_collides_for_variants():
    assert _token(KEY, "bsn", "1234.56.789") == _token(KEY, "bsn", "123456789")
    assert _token(KEY, "person", "Jansen") == _token(KEY, "person", "jansen")
    assert _token(KEY, "bsn", "123456789") != _token(KEY, "bsn", "123456788")


def test_one_stored_original_per_token_first_seen_spelling():
    """Spec: one encrypted original per token (first seen); reveal returns it;
    the normalised form is never stored; the version is recorded."""
    kp, store = InMemoryKeyProvider(), InMemoryMappingStore()
    p = Pseudonymizer(kp, store)
    first = p.anonymize("mail Jan.Jansen@Haarlem.nl").text
    second = p.anonymize("mail jan.jansen@haarlem.nl").text
    assert first == second                       # variants collide onto one token
    token = first.split()[-1]
    m = store.get(token)
    assert m is not None and m.norm_version == PROFILE_VERSION
    restored, revealed = _reveal(second, None, store.get, kp.key)
    assert restored == "mail Jan.Jansen@Haarlem.nl" and revealed == [token]
    assert "jan.jansen@haarlem.nl" not in restored  # normalised form never stored
