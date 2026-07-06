from wordsworth.states import TERMINAL, State, is_allowed


def test_registration_edge():
    assert is_allowed(None, State.REGISTERED)


def test_happy_path_edges():
    assert is_allowed(State.REGISTERED, State.EXTRACTABLE)
    assert is_allowed(State.REGISTERED, State.UNPROCESSABLE_OCR)
    assert is_allowed(State.EXTRACTABLE, State.EXTRACTED)
    assert is_allowed(State.EXTRACTED, State.ANONYMIZED)
    assert is_allowed(State.ANONYMIZED, State.INDEXED)


def test_failed_reachable_from_every_nonterminal():
    for s in (State.REGISTERED, State.EXTRACTABLE, State.EXTRACTED, State.ANONYMIZED):
        assert is_allowed(s, State.FAILED)


def test_terminal_states_have_no_outgoing_edge():
    for s in TERMINAL:
        assert not is_allowed(s, State.INDEXED)
        assert not is_allowed(s, State.FAILED)


def test_illegal_skips_are_rejected():
    assert not is_allowed(State.REGISTERED, State.INDEXED)
    assert not is_allowed(State.REGISTERED, State.ANONYMIZED)
    assert not is_allowed(State.EXTRACTABLE, State.INDEXED)
