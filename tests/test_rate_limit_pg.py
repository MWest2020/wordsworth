# SPDX-License-Identifier: MIT
"""Rate limits shared by every api replica (hoge-beschikbaarheid, step 2).

Two `PostgresTokenBucket` objects over one database stand in for two replicas:
that is exactly what two pods are, as far as the bucket can tell.
"""
import threading

from sqlalchemy import text

from wordsworth.rate_limit_pg import PostgresTokenBucket


def test_two_replicas_draw_from_one_bucket(session_factory):
    a = PostgresTokenBucket("/console/login", 0.01, 3, session_factory)
    b = PostgresTokenBucket("/console/login", 0.01, 3, session_factory)
    got = [x.check("ip:10.0.0.1").allowed for x in (a, b, a, b)]
    assert got == [True, True, True, False]


def test_a_refused_check_says_when_to_come_back(session_factory):
    bucket = PostgresTokenBucket("/search", 0.5, 1, session_factory)
    assert bucket.check("c").allowed
    d = bucket.check("c")
    assert not d.allowed and d.retry_after == 2


def test_the_bucket_refills_on_the_database_clock(session_factory):
    bucket = PostgresTokenBucket("/search", 1.0, 1, session_factory)
    assert bucket.check("c").allowed
    assert not bucket.check("c").allowed
    with session_factory() as s:   # two seconds pass, as far as Postgres knows
        s.execute(text("UPDATE rate_limit_buckets "
                       "SET updated_at = updated_at - interval '2 seconds'"))
        s.commit()
    assert bucket.check("c").allowed


def test_clients_and_endpoints_are_separate(session_factory):
    search = PostgresTokenBucket("/search", 0.01, 1, session_factory)
    ask = PostgresTokenBucket("/ask", 0.01, 1, session_factory)
    assert search.check("a").allowed
    assert search.check("b").allowed
    assert ask.check("a").allowed
    assert not search.check("a").allowed


def test_concurrent_checks_never_overspend(session_factory):
    """The row lock is the whole point: 20 simultaneous requests against a
    burst of 5 must let exactly 5 through, not 'about 5'."""
    buckets = [PostgresTokenBucket("/console/login", 0.001, 5, session_factory)
               for _ in range(2)]
    results, start = [], threading.Barrier(20)

    def hit(i):
        start.wait()
        results.append(buckets[i % 2].check("ip:10.0.0.9").allowed)

    threads = [threading.Thread(target=hit, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 5


def test_an_api_key_is_never_stored(session_factory):
    PostgresTokenBucket("/search", 1, 1, session_factory).check("key:s3cret-api-key")
    with session_factory() as s:
        clients = s.execute(text("SELECT client FROM rate_limit_buckets")).scalars().all()
    assert clients and not any("s3cret" in c for c in clients)
