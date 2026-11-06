# Design: synthetic-long-corpus

- **Building on what exists.** `wordsworth.eval.synthetic` (`Document`, `bsn`, `iban`,
  `postcode`, the name lists) stays the source of values; this adds a test-range
  BSN (`bsn_test_range`) and a non-existent-bank IBAN (`iban_fake_bank`) next to the
  existing ones rather than changing them, so `generate_ground_truth.py` keeps its
  output.
- **One `Document` per page.** Each page is built as a `Document` (text plus gold
  spans), so gold carries the page without offset arithmetic across pages. The PDF
  is written with reportlab (already a dependency); each page's text is the page's
  `Document.text`, laid out with simple wrapping.
- **Scanned pages.** Render the chosen pages with pypdfium2 (already a dependency)
  at 200 dpi and replace them with the image (reportlab `drawImage`), so the page has
  no text layer. Their gold stays; `manifest.json` lists them, so an evaluation can
  tell OCR misses from detector misses.
- **Proof that gold is true.** A test extracts every born-digital page with the
  project's own extraction (`pdf_text`) and checks every gold value of that page
  appears in it; for scanned pages it checks there is no text layer.
- **Size.** 30 × 30 pages of text is a few MB; scanned pages dominate. At the default
  10% the corpus stays well under 100 MB.
- **Test BSN range.** Working assumption: BSNs starting with `9999` are not issued
  (the range used for test environments). Recorded here; the generator only emits
  that range.
