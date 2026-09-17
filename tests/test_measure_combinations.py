# SPDX-License-Identifier: MIT
"""Counting a declared combination over the corpus (identifying-combinations)."""
import pytest

from wordsworth import pseudonym_registry
from wordsworth.measure_combinations import labels_by_document, measure
from wordsworth.pipeline import register

DECL = [{"types": ["BSN", "POSTCODE"], "reason": "bsn and postcode together"},
        {"types": ["GENDER", "DATE"], "reason": "gender and year of birth"}]


def _doc(session, key, text):
    d = register(session, key)
    pseudonym_registry.register(session, d.id, text)
    return d


def test_counts_only_documents_carrying_every_type(session):
    _doc(session, "a", "[BSN:aaaaaaaa] woont in [POSTCODE:bbbbbbbb]")
    _doc(session, "b", "[BSN:cccccccc] en verder niets")
    _doc(session, "c", "[POSTCODE:dddddddd] alleen")
    session.commit()
    both, gender = measure(session, DECL)
    assert both["documents"] == 1
    assert both["types"] == ["BSN", "POSTCODE"]
    assert both["unobservable_types"] == []


def test_a_type_the_corpus_never_carries_is_named_not_counted_as_zero(session):
    """"Does not occur" and "cannot be seen" are different answers, and a bare
    zero says the reassuring one."""
    _doc(session, "a", "[BSN:aaaaaaaa] en [POSTCODE:bbbbbbbb]")
    session.commit()
    _, gender = measure(session, DECL)
    assert gender["documents"] == 0
    assert gender["unobservable_types"] == ["DATE", "GENDER"]


def test_labels_come_from_the_registered_tokens(session):
    d = _doc(session, "a", "[BSN:aaaaaaaa] tweemaal [BSN:aaaaaaaa] en [IBAN:cccccccc]")
    session.commit()
    assert labels_by_document(session)[d.id] == {"BSN", "IBAN"}


def test_an_empty_corpus_counts_zero_and_names_everything(session):
    both, gender = measure(session, DECL)
    assert both["documents"] == 0 and both["unobservable_types"] == ["BSN", "POSTCODE"]
    assert gender["documents"] == 0


def test_a_declaration_without_a_reason_is_refused(session):
    from wordsworth.combinations import CombinationError

    with pytest.raises(CombinationError):
        measure(session, [{"types": ["BSN", "POSTCODE"]}])
