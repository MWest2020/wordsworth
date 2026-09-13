"""WORM-export van de key-lifecycle-stream (gap 28).

Dit is de stream die vertelt wie wanneer welke sleutel roteerde. De vraag komt
ná een incident, op het moment dat de host die het bestand draagt zelf verdacht
is — dus moet hij ergens staan waar hij niet meer te wijzigen valt.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wordsworth.audit_export import ExportError, InMemoryWormStore
from wordsworth.key_audit import JsonlKeyLifecycleAudit
from wordsworth.key_audit_export import export_key_lifecycle_worm


def _stream(tmp_path: Path, n: int = 2) -> JsonlKeyLifecycleAudit:
    s = JsonlKeyLifecycleAudit(tmp_path / "key_lifecycle.jsonl")
    for i in range(n):
        s.rotation(old_key_id=f"k{i}", new_key_id=f"k{i+1}",
                   entries_reencrypted=i, actor="operator")
    return s


def test_de_stream_belandt_achter_object_lock(tmp_path):
    s, store = _stream(tmp_path, 2), InMemoryWormStore()
    res = export_key_lifecycle_worm(s, store, retention_days=3650)
    assert res.count == 2
    assert res.object_key.startswith("key-lifecycle/line-")
    # Byte-voor-byte hetzelfde als de bron: een export die opnieuw serialiseert
    # is een bestand dat hetzelfde BETEKENT en anders IS, en dan kun je "klopt
    # de export met de bron" niet meer met een vergelijking beantwoorden.
    assert store.get(res.object_key).decode() == s.path.read_text()


def test_de_bewaartermijn_staat_op_het_object(tmp_path):
    s, store = _stream(tmp_path, 1), InMemoryWormStore()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    res = export_key_lifecycle_worm(s, store, retention_days=2555, now=now)
    assert res.retain_until == now + timedelta(days=2555)
    assert store.retain_until(res.object_key) == res.retain_until


def test_incrementeel_exporteren_verstuurt_alleen_het_nieuwe(tmp_path):
    s, store = _stream(tmp_path, 2), InMemoryWormStore()
    eerste = export_key_lifecycle_worm(s, store, retention_days=3650)
    s.rotation(old_key_id="k2", new_key_id="k3", entries_reencrypted=7, actor="operator")
    tweede = export_key_lifecycle_worm(s, store, retention_days=3650,
                                       after_line=eerste.last_seq)
    assert tweede.count == 1
    assert "k3" in store.get(tweede.object_key).decode()
    assert "k1" not in store.get(tweede.object_key).decode()


def test_niets_nieuws_is_geen_fout(tmp_path):
    # Een stream die stilstond is geen mislukte export. Dit onderscheid is de
    # reden dat een geplande run niet elke nacht alarm slaat.
    s, store = _stream(tmp_path, 2), InMemoryWormStore()
    res = export_key_lifecycle_worm(s, store, retention_days=3650, after_line=2)
    assert res.count == 0 and res.object_key is None


def test_een_lege_stream_exporteert_niets(tmp_path):
    s = JsonlKeyLifecycleAudit(tmp_path / "leeg.jsonl")
    res = export_key_lifecycle_worm(s, InMemoryWormStore(), retention_days=3650)
    assert res.count == 0 and res.object_key is None


def test_een_store_die_iets_anders_teruggeeft_is_een_harde_fout(tmp_path):
    class Liegende(InMemoryWormStore):
        def get(self, key):
            return b"iets anders\n"

    with pytest.raises(ExportError, match="does not match"):
        export_key_lifecycle_worm(_stream(tmp_path, 1), Liegende(), retention_days=3650)


def test_grants_staan_er_ook_in(tmp_path):
    # De stream draagt meer dan rotaties: uitgifte en intrekking van grants
    # horen bij dezelfde vraag ("wie mocht wat, wanneer").
    s = JsonlKeyLifecycleAudit(tmp_path / "key_lifecycle.jsonl")
    s.grant_issued(grant_id="g1", recipient="r", allowed_types=["BSN"],
                   document_id=None, actor="operator")
    s.grant_revoked(grant_id="g1", actor="operator")
    store = InMemoryWormStore()
    res = export_key_lifecycle_worm(s, store, retention_days=3650)
    inhoud = store.get(res.object_key).decode()
    assert "grant_issued" in inhoud and "grant_revoked" in inhoud
    # En geen sleutelmateriaal — de stream draagt id's, nooit sleutels.
    assert "BEGIN" not in inhoud
