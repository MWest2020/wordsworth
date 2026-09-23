# SPDX-License-Identifier: MIT
"""A token bucket shared by every api replica (hoge-beschikbaarheid, step 2).

`TokenBucket` keeps its state in the process. With two replicas every client
gets two buckets, and every limit -- including the one on `/console/login`,
where each request is a guess at the key set -- quietly doubles. This bucket has
the same contract (`check(key) -> Decision`) but its state and its clock are
Postgres's, so all replicas draw from one bucket.

One statement per check. `INSERT ... ON CONFLICT DO UPDATE` takes the row lock,
refills, decides and spends in one go, so two replicas checking the same client
at the same moment are serialised by the database, not by luck. The clock is
`now()` on the database server: replica clocks never enter the arithmetic.

The client key is stored hashed. `client_key()` is `key:<the API key itself>`
for a keyed caller, and a rate-limit table is no place for credentials.

Fails closed: if Postgres is unreachable the check raises and the request is a
500. The limited endpoints need the database anyway, except `/console/login`;
refusing a login while the database is down is the safe side.
"""
from __future__ import annotations

import hashlib
import math

from sqlalchemy import text

from .rate_limit import Decision

_CHECK_SQL = text("""
INSERT INTO rate_limit_buckets AS b (bucket, client, tokens, allowed, updated_at)
VALUES (:bucket, :client,
        CASE WHEN :burst >= 1 THEN :burst - 1 ELSE :burst END,
        :burst >= 1, now())
ON CONFLICT (bucket, client) DO UPDATE SET
    allowed = LEAST(:burst, b.tokens
                    + EXTRACT(EPOCH FROM now() - b.updated_at) * :rate) >= 1,
    tokens = LEAST(:burst, b.tokens + EXTRACT(EPOCH FROM now() - b.updated_at) * :rate)
             - CASE WHEN LEAST(:burst, b.tokens
                               + EXTRACT(EPOCH FROM now() - b.updated_at) * :rate) >= 1
                    THEN 1 ELSE 0 END,
    updated_at = now()
RETURNING allowed, tokens
""")


class PostgresTokenBucket:
    """`TokenBucket` with its state in `rate_limit_buckets`."""

    def __init__(self, name: str, rate: float, burst: float, session_factory) -> None:
        if rate <= 0 or burst <= 0:
            raise ValueError("rate and burst must be positive")
        self._name = name
        self._rate = float(rate)
        self._burst = float(burst)
        self._sessions = session_factory

    def check(self, key: str) -> Decision:
        client = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with self._sessions() as s:
            allowed, tokens = s.execute(_CHECK_SQL, {
                "bucket": self._name, "client": client,
                "rate": self._rate, "burst": self._burst}).one()
            s.commit()
        if allowed:
            return Decision(allowed=True, retry_after=0)
        return Decision(allowed=False,
                        retry_after=max(1, math.ceil((1.0 - tokens) / self._rate)))
