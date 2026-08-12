"""wordsworthctl client — offline bits (no server contacted)."""
from __future__ import annotations

from wordsworth.client import _iter_files, main


def test_iter_files_pdf_recursive_and_all(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "note.txt").write_text("x")

    pdfs = _iter_files(tmp_path, include_all=False)
    assert {p.name for p in pdfs} == {"a.pdf", "b.pdf"}  # recursive, pdf-only

    everything = _iter_files(tmp_path, include_all=True)
    assert {p.name for p in everything} == {"a.pdf", "b.pdf", "note.txt"}


def test_iter_files_single_file(tmp_path):
    f = tmp_path / "only.pdf"
    f.write_bytes(b"%PDF-1.4")
    assert _iter_files(f, include_all=False) == [f]


def test_ingest_missing_path_exits_nonzero(tmp_path):
    assert main(["--url", "http://unused", "ingest", str(tmp_path / "nope")]) == 2
