import re
from uuid import UUID

from sqlalchemy import select

from wordsworth import audit
from wordsworth.escrow import AgeEscrow
from wordsworth.key_audit import ROTATION_ACTION, STREAM, JsonlKeyLifecycleAudit
from wordsworth.key_lifecycle import rotate_keys
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord, Document, DocumentText
from wordsworth.pipeline import register
from wordsworth.pseudonymizer import Pseudonymizer, deanonymize

SENTINEL_ID = UUID("00000000-0000-0000-0000-000000000000")

PII_BSN = "123456782"
PII_IBAN = "NL91ABNA0417164300"

_PSEUDO_RE = re.compile(r"\[[A-Z]+:[0-9a-f]{8}\]")


# --- Task 2.2: key selection by stored key_id (no re-encryption) ------------

def test_mixed_pre_and_post_rotation_mappings_all_decrypt(session):
    kp = InMemoryKeyProvider()
    store = PostgresMappingStore(session)
    doc = register(session, "d")
    session.commit()

    pre = Pseudonymizer(kp, store).anonymize(f"BSN {PII_BSN}")
    session.commit()
    old_id = kp.current_key().id

    kp.rotate()  # new active key, mappings NOT re-encrypted
    new_id = kp.current_key().id
    assert old_id != new_id

    post = Pseudonymizer(kp, store).anonymize(f"IBAN {PII_IBAN}")
    session.commit()

    # the two mappings live under different key ids
    assert store.get(_PSEUDO_RE.search(pre.text).group(0)).key_id == old_id
    assert store.get(_PSEUDO_RE.search(post.text).group(0)).key_id == new_id

    restored = deanonymize(
        session, doc.id, pre.text + " " + post.text, kp, store, actor="mark"
    )
    session.commit()
    assert PII_BSN in restored and PII_IBAN in restored


# --- Task 3.2: re-encryption; documents untouched ---------------------------

def test_reencrypt_moves_entries_to_new_key_documents_untouched(session):
    kp = InMemoryKeyProvider()
    store = PostgresMappingStore(session)
    doc = register(session, "d")
    session.commit()

    result = Pseudonymizer(kp, store).anonymize(f"BSN {PII_BSN} IBAN {PII_IBAN}")
    # the anonymized text is a document artifact — it must not change on rotation
    session.add(DocumentText(document_id=doc.id, anonymized_text=result.text))
    session.commit()

    old_id = kp.current_key().id
    new = kp.rotate()
    count = store.reencrypt(old_id, new.id, kp)
    session.commit()

    pseudonyms = _PSEUDO_RE.findall(result.text)
    assert count == len(pseudonyms) >= 2
    for pseudo in pseudonyms:
        assert store.get(pseudo).key_id == new.id  # every entry now on new key

    # the document artifact is byte-for-byte unchanged
    assert session.get(DocumentText, doc.id).anonymized_text == result.text

    # and it still deanonymizes, now via the new key
    restored = deanonymize(
        session, doc.id, result.text, kp, store, actor="x"
    )
    for secret in (PII_BSN, PII_IBAN):
        assert secret in restored


# --- Task 2.1: rotation audits to the key-lifecycle stream, not the chain ---

def test_rotation_writes_key_stream_event_document_chain_unchanged(session, tmp_path):
    kp = InMemoryKeyProvider()
    store = PostgresMappingStore(session)
    escrow = AgeEscrow()
    key_audit = JsonlKeyLifecycleAudit(tmp_path / "key-audit.jsonl")
    doc = register(session, "d")
    session.commit()

    Pseudonymizer(kp, store).anonymize(f"BSN {PII_BSN}")
    session.commit()
    old = kp.current_key()

    chain_before = [
        (r.seq, r.hash)
        for r in session.execute(
            select(AuditRecord).order_by(AuditRecord.seq)
        ).scalars()
    ]

    new = rotate_keys(kp, store, escrow, key_audit, actor="mark")
    session.commit()

    # the key-lifecycle stream gains exactly one rotation event
    events = key_audit.events()
    assert len(events) == 1
    event = events[0]
    assert event["stage"] == STREAM and event["action"] == ROTATION_ACTION
    assert event["old_key_id"] == old.id
    assert event["new_key_id"] == new.id
    assert event["actor"] == "mark"
    assert event["entries_reencrypted"] >= 1

    # no key material is ever logged — only ids
    raw = (tmp_path / "key-audit.jsonl").read_text(encoding="utf-8")
    assert new.material.hex() not in raw
    assert old.material.hex() not in raw
    assert old.id in raw and new.id in raw

    # the document hash-chain gains no record and still verifies
    chain_after = [
        (r.seq, r.hash)
        for r in session.execute(
            select(AuditRecord).order_by(AuditRecord.seq)
        ).scalars()
    ]
    assert chain_after == chain_before
    ok, bad = audit.verify_chain(session)
    assert ok is True and bad is None

    # no phantom document was created
    assert set(session.execute(select(Document.id)).scalars()) == {doc.id}


# --- Task 2.2: no sentinel document; deanonymize survives rotation ----------

def test_no_sentinel_document_and_deanonymize_by_key_id_survives_rotation(
    session, tmp_path
):
    kp = InMemoryKeyProvider()
    store = PostgresMappingStore(session)
    escrow = AgeEscrow()
    key_audit = JsonlKeyLifecycleAudit(tmp_path / "key-audit.jsonl")
    doc = register(session, "d")
    session.commit()

    pre = Pseudonymizer(kp, store).anonymize(f"BSN {PII_BSN}")
    session.commit()

    new = rotate_keys(kp, store, escrow, key_audit, actor="mark")
    session.commit()

    post = Pseudonymizer(kp, store).anonymize(f"IBAN {PII_IBAN}")
    session.commit()

    # no 00000000-… sentinel/system document exists anywhere
    assert session.get(Document, SENTINEL_ID) is None
    audited_ids = set(session.execute(select(AuditRecord.document_id)).scalars())
    assert SENTINEL_ID not in audited_ids
    # a real document's history is only its own records
    assert audited_ids == {doc.id}

    # deanonymize-by-key_id decrypts pre-rotation (re-encrypted) and
    # post-rotation mappings alike
    restored = deanonymize(
        session, doc.id, pre.text + " " + post.text, kp, store, actor="r"
    )
    session.commit()
    assert PII_BSN in restored and PII_IBAN in restored

    # escrow recovery unchanged: a fresh provider holding only the recovered
    # key still decrypts the re-encrypted pre-rotation mapping
    fresh = InMemoryKeyProvider(initial=escrow.recover(new.id))
    restored2 = deanonymize(session, doc.id, pre.text, fresh, store, actor="r")
    session.commit()
    assert PII_BSN in restored2
