"""add-legible-placeholders: numbered Dutch placeholders as a VIEW; stored text,
tokens and reveal untouched."""
import io
import zipfile

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.legible import to_legible
from wordsworth.pipeline import get_anonymized_text, ingest, process


def test_same_token_same_ordinal_and_legend():
    text = ("[PERSON:3fa9c2d1] belt [PERSON:9b0e11aa]; later weer [PERSON:3fa9c2d1] "
            "in [LOCATION:0000abcd] met [BSN:12345678] en [ZZ_TYPE:deadbeef].")
    out, legend = to_legible(text)
    assert out == ("[PERSOON 1] belt [PERSOON 2]; later weer [PERSOON 1] in "
                   "[LOCATIE 1] met [BSN 1] en [ZZ_TYPE 1].")
    assert legend == {"[PERSOON 1]": "[PERSON:3fa9c2d1]", "[PERSOON 2]": "[PERSON:9b0e11aa]",
                      "[LOCATIE 1]": "[LOCATION:0000abcd]", "[BSN 1]": "[BSN:12345678]",
                      "[ZZ_TYPE 1]": "[ZZ_TYPE:deadbeef]"}
    assert sum(1 for k in legend if k.startswith("[PERSOON")) == 2


def test_no_tokens_is_identity():
    assert to_legible("gewone tekst [BSN] zonder tokens") == (
        "gewone tekst [BSN] zonder tokens", {})


def _prepare(session_factory, mem_store, mem_index, fake_embedder, pdf):
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.mapping_store import PostgresMappingStore
    from wordsworth.pseudonymizer import Pseudonymizer
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(InMemoryKeyProvider(), PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        return doc.id, get_anonymized_text(s, doc.id)


def test_anonymized_endpoint_views(session_factory, mem_store, mem_index,
                                   fake_embedder, born_digital_pii_pdf):
    doc_id, stored = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                              born_digital_pii_pdf)
    c = TestClient(create_app(session_factory=session_factory))
    default = c.get(f"/documents/{doc_id}/anonymized").json()
    assert default["anonymized_text"] == stored and default["view"] == "tokens"
    assert default["legend"] is None
    legible = c.get(f"/documents/{doc_id}/anonymized", params={"view": "legible"}).json()
    assert "[BSN 1]" in legible["anonymized_text"] and "[EMAIL 1]" in legible["anonymized_text"]
    assert "[BSN:" not in legible["anonymized_text"]
    assert legible["legend"]["[BSN 1]"].startswith("[BSN:")
    with session_factory() as s:  # nothing stored changed
        assert get_anonymized_text(s, doc_id) == stored
    assert c.get(f"/documents/{doc_id}/anonymized", params={"view": "x"}).status_code == 400


def test_zip_export_legible(session_factory, mem_store, mem_index,
                            fake_embedder, born_digital_pii_pdf):
    doc_id, stored = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                              born_digital_pii_pdf)
    c = TestClient(create_app(session_factory=session_factory))
    r = c.get("/export/anonymized.zip", params={"view": "legible"})
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        body = zf.read(f"{doc_id}.txt").decode()
    assert "[IBAN 1]" in body and "[IBAN:" not in body
    plain = c.get("/export/anonymized.zip").content
    with zipfile.ZipFile(io.BytesIO(plain)) as zf:
        assert zf.read(f"{doc_id}.txt").decode() == stored
