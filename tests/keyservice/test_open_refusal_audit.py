"""design.md "The 429 audit": one ``open_refused`` record per caller per
60-second window, written lazily by the first refusal of the next one,
with an ``open_refused_summary`` naming the previous window's count --
never one chained write per refusal."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wordsworth.keyservice import limits, state
from wordsworth.keyservice.models_access import AccessAudit


def _refuse(session_factory, *, caller, now):
    decision = limits.check(
        session_factory, caller=caller, rate_per_minute=60, burst=0, now=now)
    assert not decision.allowed
    return decision


def _counter(session_factory, *, caller, reason="rate"):
    with session_factory() as session:
        counters = dict(state.refusal_counters(session))
    key = f'keyservice_open_refusals_total{{caller="{caller}",reason="{reason}"}}'
    return counters.get(key, 0)


def test_500_refusals_in_one_window_write_one_record_with_that_count(
        keyservice_session_factory):
    now = datetime.now(timezone.utc)
    for _ in range(500):
        _refuse(keyservice_session_factory, caller="ingest", now=now)

    with keyservice_session_factory() as session:
        refused = [r for r in session.query(AccessAudit).all()
                   if r.event == "open_refused"]
    assert len(refused) == 1
    assert _counter(keyservice_session_factory, caller="ingest") == 500


def test_a_refusal_in_the_next_window_writes_the_summary_and_a_new_record(
        keyservice_session_factory):
    now = datetime.now(timezone.utc)
    for _ in range(500):
        _refuse(keyservice_session_factory, caller="ingest", now=now)

    later = now + timedelta(seconds=61)
    _refuse(keyservice_session_factory, caller="ingest", now=later)

    with keyservice_session_factory() as session:
        refused = [r for r in session.query(AccessAudit).all()
                   if r.event == "open_refused"]
        summaries = [r for r in session.query(AccessAudit).all()
                     if r.event == "open_refused_summary"]
    assert len(refused) == 2
    assert len(summaries) == 1
    assert summaries[0].payload["count"] == 500
    assert _counter(keyservice_session_factory, caller="ingest") == 501


def test_a_caller_never_refused_again_leaves_its_last_window_unsummarised(
        keyservice_session_factory):
    now = datetime.now(timezone.utc)
    _refuse(keyservice_session_factory, caller="ingest", now=now)
    _refuse(keyservice_session_factory, caller="ingest", now=now)

    with keyservice_session_factory() as session:
        summaries = [r for r in session.query(AccessAudit).all()
                     if r.event == "open_refused_summary"]
    assert summaries == []
    assert _counter(keyservice_session_factory, caller="ingest") == 2
