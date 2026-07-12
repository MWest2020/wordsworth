import re

from sqlalchemy import select

from wordsworth import audit
from wordsworth.escrow import AgeEscrow
from wordsworth.key_lifecycle import ROTATION_STEP, rotate_keys
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord, DocumentText
from wordsworth.pipeline import register
from wordsworth.pseudonymizer import Pseudonymizer, deanonymize

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


# --- Tasks 4.2 / 4.3: rotation audit record + escrow recovery ----------------

def test_rotate_keys_audits_without_key_material_and_recovers(session):
    kp = InMemoryKeyProvider()
    store = PostgresMappingStore(session)
    escrow = AgeEscrow()
    doc = register(session, "d")
    session.commit()

    result = Pseudonymizer(kp, store).anonymize(f"BSN {PII_BSN}")
    session.commit()
    old_id = kp.current_key().id

    new = rotate_keys(session, kp, store, escrow, actor="mark")
    session.commit()

    record = session.execute(
        select(AuditRecord).where(AuditRecord.step == ROTATION_STEP)
    ).scalar_one()
    assert record.payload["old_key_id"] == old_id
    assert record.payload["new_key_id"] == new.id
    assert record.payload["actor"] == "mark"
    assert record.payload["entries_reencrypted"] >= 1
    # no key material is ever logged
    body = str(record.payload)
    assert new.material.hex() not in body
    assert old_id in body  # ids are fine; material is not

    ok, bad = audit.verify_chain(session)
    assert ok is True and bad is None

    # recovery: a fresh provider holding only the recovered key still decrypts
    recovered = escrow.recover(new.id)
    fresh = InMemoryKeyProvider(initial=recovered)
    restored = deanonymize(session, doc.id, result.text, fresh, store, actor="r")
    session.commit()
    assert PII_BSN in restored
