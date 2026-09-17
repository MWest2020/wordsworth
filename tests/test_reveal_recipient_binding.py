"""Een grant noemt WIE mag onthullen — tot dat gecontroleerd wordt is het een bearer-token.

`Grant.recipient` bestond, werd bij uitgifte gevraagd en verscheen in de audit,
maar `authorize()` keek er nooit naar. Daarmee onthulde iedereen met het
grant-id: één lek uit een logregel, een ticket of een screenshot, en klare PII
ligt open voor wie hem vindt.

Een security-review noemde dit; het werd bewust doorgeschoven omdat het de
betekenis van een grant raakt. Sinds het uitgeven beperkt is tot een expliciete
kring en de documentscope wordt afgedwongen, was dit de zwakste schakel.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from wordsworth.grants import ACTIVE, Grant, authorize

NU = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
DOC = uuid.uuid4()


def _grant(recipient: str = "console", **kw) -> Grant:
    velden = dict(
        grant_id=str(uuid.uuid4()), recipient=recipient, allowed_types=["PERSON"],
        document_id=DOC, status=ACTIVE, created_at=NU, revoked_at=None,
        expires_at=NU + timedelta(days=1), actor="mark",
    )
    velden.update(kw)
    return Grant(**velden)


def test_zonder_auth_verandert_er_niets():
    """De bestaande, gedocumenteerde tailnet-interne modus: geen caller om op te
    beslissen, dus geen nieuwe weigering."""
    assert authorize(_grant(), DOC, {"PERSON"}, NU, caller=None,
                     auth_enabled=False) == {"PERSON"}
    assert authorize(_grant(), DOC, {"PERSON"}, NU, caller="iemand-anders",
                     auth_enabled=False) == {"PERSON"}


def test_de_recipient_mag():
    assert authorize(_grant("console"), DOC, {"PERSON"}, NU, caller="console",
                     auth_enabled=True) == {"PERSON"}


def test_een_ander_mag_niet():
    """Dit is het lek: een geldig grant-id in verkeerde handen."""
    assert authorize(_grant("console"), DOC, {"PERSON"}, NU, caller="cli",
                     auth_enabled=True) == set()


def test_geen_caller_met_auth_aan_is_een_weigering():
    """Fail-closed: auth staat aan maar we weten niet wie belt."""
    assert authorize(_grant("console"), DOC, {"PERSON"}, NU, caller=None,
                     auth_enabled=True) == set()


def test_de_vergelijking_is_exact():
    """Geen hoofdletterongevoeligheid, geen prefix, geen wildcard. Twee labels die
    op elkaar lijken zijn niet hetzelfde label, en een reveal is de verkeerde
    plek om ruimhartig te zijn."""
    g = _grant("console")
    for bijna in ("Console", "CONSOLE", "console-2", "conso", "console*", ""):
        assert authorize(g, DOC, {"PERSON"}, NU, caller=bijna,
                         auth_enabled=True) == set(), bijna


def test_omringende_spatie_is_transport_geen_andere_naam():
    assert authorize(_grant("console"), DOC, {"PERSON"}, NU, caller=" console ",
                     auth_enabled=True) == {"PERSON"}


def test_de_recipient_omzeilt_de_andere_controles_niet():
    """De juiste caller op een ingetrokken grant blijft een weigering."""
    assert authorize(_grant("console", status="revoked"), DOC, {"PERSON"}, NU,
                     caller="console", auth_enabled=True) == set()
    verlopen = _grant("console", expires_at=NU - timedelta(seconds=1))
    assert authorize(verlopen, DOC, {"PERSON"}, NU, caller="console",
                     auth_enabled=True) == set()
    ander_doc = _grant("console", document_id=uuid.uuid4())
    assert authorize(ander_doc, DOC, {"PERSON"}, NU, caller="console",
                     auth_enabled=True) == set()
