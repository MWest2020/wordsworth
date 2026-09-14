"""De schema-migratie wacht niet eeuwig op een lock (DB-backed, skipt zonder DB).

Beide statements in `init_schema` hebben ACCESS EXCLUSIVE nodig op een tabel
waar de api uit leest. Een geblokkeerde migratie wácht niet alleen: een
wachtend ACCESS EXCLUSIVE-verzoek zet elke latere lezer erachter in de rij, dus
één vastgelopen init trekt de hele api mee.

Op 2026-09-14 werd zo'n init tijdens een lopende reprocess opgebroken door
Postgres' eigen deadlock-detectie. Dat is geluk, geen ontwerp: bij een gewone
lock-wachtrij zonder cyclus grijpt die detectie niet in en wacht hij door.

Snel falen is de betere helft van de afspraak — het init-Job probeert het
opnieuw, en een poging een seconde later vindt de lock meestal vrij.
"""
from __future__ import annotations

import time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from wordsworth.db import init_schema, make_engine


def test_een_geblokkeerde_migratie_faalt_snel_in_plaats_van_te_hangen(database_url):
    blokkeerder = make_engine(database_url)
    with blokkeerder.connect() as conn:
        conn.execute(text("BEGIN"))
        # ACCESS EXCLUSIVE botst met alles, ook met zichzelf.
        conn.execute(text("LOCK TABLE audit_records IN ACCESS EXCLUSIVE MODE"))
        t0 = time.monotonic()
        with pytest.raises(OperationalError) as fout:
            init_schema(make_engine(database_url))
        duur = time.monotonic() - t0
        conn.execute(text("ROLLBACK"))

    assert "lock" in str(fout.value).lower()          # het was de lock, niet iets anders
    assert duur < 20, f"duurde {duur:.1f}s — de grens van 5s greep niet in"


def test_migratie_loopt_gewoon_door_zonder_tegenstander(database_url):
    init_schema(make_engine(database_url))            # idempotent, moet stil slagen
