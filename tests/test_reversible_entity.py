"""Reversible entity pseudonymisation — pure/local, no DB, no service
(add-reversible-entity-pseudonymization).

A fake detection engine stands in for OpenAnonymiser so the entity path is
provable in memory; the DB-backed deanonymize/audit path is covered in
tests/test_pseudonymizer.py (CI runs it against a real Postgres)."""
from __future__ import annotations

import re

import pytest

from wordsworth.anonymizer import Anonymizer
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.openanonymiser_driver import AnonymizationEngineError, Entity
from wordsworth.pseudonymizer import ReversibleAnonymizer, _reveal

PII_BSN = "111222333"        # passes the elfproef
NAME = "Jan Jansen"


def _detect_all(name: str):
    def detect(text: str) -> list[Entity]:
        out, start = [], 0
        while (i := text.find(name, start)) >= 0:
            out.append(Entity("PERSON", name, i, i + len(name)))
            start = i + len(name)
        return out
    return detect


def _driver(name: str = NAME):
    kp = InMemoryKeyProvider()
    store = InMemoryMappingStore()
    return kp, store, ReversibleAnonymizer(kp, store, detect=_detect_all(name))


def test_satisfies_anonymizer_protocol():
    _, _, drv = _driver()
    assert isinstance(drv, Anonymizer)


def test_entity_and_deterministic_compose_no_clear_pii():
    kp, store, drv = _driver()
    res = drv.anonymize(f"{NAME} met BSN {PII_BSN}")
    assert NAME not in res.text and PII_BSN not in res.text
    assert "[PERSON:" in res.text and "[BSN:" in res.text   # both types tokenised
    assert res.counts.get("person") == 1 and res.counts.get("bsn") == 1


def test_entity_keyed_under_its_type_key():
    kp, store, drv = _driver()
    drv.anonymize(f"{NAME} BSN {PII_BSN}")
    person = next(p for p in store._d if p.startswith("[PERSON:"))
    bsn = next(p for p in store._d if p.startswith("[BSN:"))
    assert store.get(person).key_id == kp.current_key(scope="PERSON").id
    assert store.get(person).key_id != store.get(bsn).key_id   # per-type keys


def test_selective_reveal_person_not_bsn():
    kp, store, drv = _driver()
    pseudo = drv.anonymize(f"{NAME} BSN {PII_BSN}").text
    restored, revealed = _reveal(pseudo, {"PERSON"}, store.get, kp.key)
    assert NAME in restored                       # allowed type revealed
    assert PII_BSN not in restored and "[BSN:" in restored
    assert all(r.startswith("[PERSON:") for r in revealed)


def test_reveal_all_recovers_both_types():
    kp, store, drv = _driver()
    pseudo = drv.anonymize(f"{NAME} BSN {PII_BSN}").text
    restored, _ = _reveal(pseudo, None, store.get, kp.key)
    assert NAME in restored and PII_BSN in restored


def test_stable_pseudonym_same_name():
    kp, store, drv = _driver()
    res = drv.anonymize(f"{NAME} en nogmaals {NAME}")
    tokens = re.findall(r"\[PERSON:[0-9a-f]{8}\]", res.text)
    assert len(tokens) == 2 and len(set(tokens)) == 1


def test_detection_failure_is_fail_hard_no_leak():
    kp = InMemoryKeyProvider()
    store = InMemoryMappingStore()

    def boom(text: str) -> list[Entity]:
        raise RuntimeError("engine down")

    drv = ReversibleAnonymizer(kp, store, detect=boom)
    with pytest.raises(AnonymizationEngineError) as ei:
        drv.anonymize(f"{NAME} BSN {PII_BSN}")
    assert NAME not in str(ei.value)              # error carries no clear text


def test_redaction_is_offset_independent_no_leak():
    # The audit's HIGH finding: the service can report offsets that do not match
    # Python char slicing (byte-vs-char on non-ASCII Dutch text). Redaction must
    # match the VALUE, never the offsets — a bad offset must not leak clear PII.
    kp = InMemoryKeyProvider()
    store = InMemoryMappingStore()

    def detect(text: str) -> list[Entity]:
        return [Entity("PERSON", "Jan Jansen", 999, 1009)]  # deliberately wrong span

    drv = ReversibleAnonymizer(kp, store, detect=detect)
    res = drv.anonymize("Beste Renée, contact Jan Jansen alstublieft.")
    assert "Jan Jansen" not in res.text          # no leak despite bogus offsets
    assert "[PERSON:" in res.text
    restored, _ = _reveal(res.text, None, store.get, kp.key)
    assert "Jan Jansen" in restored


def test_all_occurrences_of_a_value_are_redacted():
    kp, store, drv = _driver("Renée")
    res = drv.anonymize("Renée en Renée en nog eens Renée")
    assert "Renée" not in res.text
    assert res.text.count("[PERSON:") == 3


def test_underscored_entity_type_is_revealable():
    kp = InMemoryKeyProvider()
    store = InMemoryMappingStore()

    def detect(text: str) -> list[Entity]:
        return [Entity("PHONE_NUMBER", "0612345678", 0, 10)]

    drv = ReversibleAnonymizer(kp, store, detect=detect)
    res = drv.anonymize("bel 0612345678 vandaag")
    assert "0612345678" not in res.text and "[PHONE_NUMBER:" in res.text
    restored, revealed = _reveal(res.text, None, store.get, kp.key)
    assert "0612345678" in restored and revealed   # widened token regex matches


def test_short_noise_entities_are_skipped_no_false_failhard():
    # GLiNER emits spurious 1-2 char spans on OCR-noisy Dutch text (e.g. "ik")
    # that recur throughout ordinary text; redacting them would trip the fail-hard
    # survivor check and wrongly reject the whole document. They must be skipped,
    # while a real (>=3 char) entity is still pseudonymised.
    kp = InMemoryKeyProvider()
    store = InMemoryMappingStore()

    def detect(text: str) -> list[Entity]:
        return [Entity("PERSON", "ik", 0, 2), Entity("PERSON", "Jan Jansen", 12, 22)]

    drv = ReversibleAnonymizer(kp, store, detect=detect)
    res = drv.anonymize("ik denk dat Jan Jansen ook ik zei")  # "ik" recurs
    assert "Jan Jansen" not in res.text and "[PERSON:" in res.text  # real entity gone
    assert "ik" in res.text                # 2-char noise left as-is, no fail-hard
    assert res.counts.get("person") == 1   # only the real entity counted


def test_fragment_inside_a_word_is_not_redacted_or_failhard():
    # GLiNER emits >=3-char fragment spans on OCR-noisy text (e.g. "ene" inside
    # "voorzienen"). Word-boundary matching must NOT redact the fragment inside a
    # larger word (no mangling) nor trip the survivor fail-hard, while a real
    # whole-word entity is still redacted.
    kp = InMemoryKeyProvider()
    store = InMemoryMappingStore()

    def detect(text: str) -> list[Entity]:
        return [Entity("PERSON", "ene", 0, 3), Entity("PERSON", "Jan Jansen", 4, 14)]

    drv = ReversibleAnonymizer(kp, store, detect=detect)
    res = drv.anonymize("de voorzienen van Jan Jansen")  # "ene" only inside a word
    assert "voorzienen" in res.text          # word intact, fragment not redacted
    assert "Jan Jansen" not in res.text and "[PERSON:" in res.text  # real entity gone


def test_overlapping_spans_longer_wins():
    kp = InMemoryKeyProvider()
    store = InMemoryMappingStore()

    def detect(text: str) -> list[Entity]:
        return [Entity("PERSON", "Jan Jansen", 0, 10), Entity("PERSON", "Jan", 0, 3)]

    drv = ReversibleAnonymizer(kp, store, detect=detect)
    res = drv.anonymize("Jan Jansen")
    assert res.text.count("[PERSON:") == 1        # inner overlap skipped
    restored, _ = _reveal(res.text, None, store.get, kp.key)
    assert restored == "Jan Jansen"
