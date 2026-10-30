"""The film's scenes. A scene's captions are the sentences of its proven claims, in the
order of docs/reference/film-claims.yml; each visual fragment names the claim it shows
(`None` = always there while the scene is) and appears when that claim is spoken
(`data-at`, plus `data-dt` seconds). A scene with no proven claim is left out.
`{name}` in a fragment takes a value from the claims' checks."""

DOCS = "".join(
    f'<div class="doc">' + "".join(f'<div class="ln w{(i + k) % 3}"></div>' for k in range(6))
    + '<span class="pii-bar" data-at="pii-found" data-dt="0.5"></span></div>' for i in range(6))

SCENES = [
    {"key": "probleem", "title": "Een Woo-publicatie: honderden documenten", "body": [
        (None, f'<div class="docs">{DOCS}</div>'),
        ("pilot-corpus", '<p class="big" data-at="pilot-corpus" data-dt="1.0">{documents} documenten in één publicatie</p>'),
        ("pii-found", '<p class="note" data-at="pii-found">{persons} namen · {phones} telefoonnummers gemarkeerd</p>'),
    ]},
    {"key": "straat", "title": "Wat wordsworth doet", "body": [
        (None, '<div class="steps">'),
        ("pipeline-read", '<div class="step" data-at="pipeline-read">Inlezen</div>'
                          '<div class="arrow" data-at="pipeline-read" data-dt="0.6">→</div>'
                          '<div class="step" data-at="pipeline-read" data-dt="1.0">Tekst</div>'),
        ("detect-two-layers", '<div class="arrow" data-at="detect-two-layers">→</div>'
                              '<div class="step" data-at="detect-two-layers" data-dt="0.3">Persoons&shy;gegevens vinden</div>'),
        ("tokens-before-index", '<div class="arrow" data-at="tokens-before-index">→</div>'
                                '<div class="step dark" data-at="tokens-before-index" data-dt="0.3">Vervangen door codes</div>'
                                '<div class="arrow" data-at="tokens-before-index" data-dt="1.0">→</div>'
                                '<div class="step" data-at="tokens-before-index" data-dt="1.4">Doorzoekbaar</div>'),
        (None, '</div>'),
        ("tokens-before-index", '<div class="sentence" data-at="tokens-before-index" data-dt="0.5">Op 12 maart meldde '
                                '<span class="pii" data-swap="tokens-before-index" data-dt="2.5"><span class="v">Anna de Wit</span>'
                                '<span class="t">Persoon 1</span></span> bezwaar bij de gemeente '
                                '<span class="pii" data-swap="tokens-before-index" data-dt="2.9"><span class="v">Zuiderdorp</span>'
                                '<span class="t">Locatie 1</span></span>.</div>'
                                '<p class="note" data-at="tokens-before-index" data-dt="0.5">Voorbeeld met verzonnen gegevens.</p>'),
    ]},
    {"key": "zoeken", "title": "Zoeken op woorden én op betekenis", "body": [
        ("hybrid-search", '<div class="search" data-at="hybrid-search">noodopvang asielzoekers<span class="caret"></span></div>'
                          '<div class="results"><div class="res" data-at="hybrid-search" data-dt="1.0"><b>1</b> Woo-verzoek: noodopvang '
                          '<span class="tok">Persoon 1</span></div><div class="res" data-at="hybrid-search" data-dt="1.4"><b>2</b> '
                          'Raadsvoorstel: opvanglocaties <span class="tok">Organisatie 2</span></div></div>'),
        ("topics", '<div class="topics"><span class="chip" data-at="topics">{topics} onderwerpen</span>'
                   '<span class="chip" data-at="topics" data-dt="0.4">voorbeeld: Asielopvang</span></div>'),
        (None, '<p class="note">Voorbeeld met verzonnen gegevens.</p>'),
    ]},
    {"key": "index", "title": "Wat staat er in de zoekindex?", "body": [
        (None, '<div class="ix">'),
        ("index-codes", '<div class="ix-index" data-at="index-codes"><div class="ix-h">Zoekindex</div>'
                        '<div class="ix-row">… gemeld door <span class="tok">[PERSOON 7c2a]</span></div>'
                        '<div class="ix-row">… locatie <span class="tok">[LOCATIE 19be]</span></div>'
                        '<div class="ix-no" data-at="index-codes" data-dt="2.0">✕ geen echte waarden, ook niet versleuteld</div></div>'),
        ("index-why", '<div class="ix-whys"><div class="ix-why" data-at="index-why">Versleutelde tekst: niet doorzoekbaar</div>'
                      '<div class="ix-why" data-at="index-why" data-dt="2.5">Zoekmachine die ontsleutelt: bewaart sleutels én persoonsgegevens</div></div>'),
        ("reveal-after", '<div class="ix-doc" data-at="reveal-after"><div class="ix-h">Document · na het zoeken</div>'
                         '<div class="ix-row">Gemeld door <span class="pii rv" data-swap="reveal-after" data-dt="2.0"><span class="t">[PERSOON 7c2a]</span>'
                         '<span class="v">Jan Jansen</span></span></div><div class="ix-key" data-at="reveal-after" data-dt="3.0">'
                         'recht: alleen PERSOON · in het geheugen · gelogd</div><div class="note">Voorbeeld met verzonnen gegevens.</div></div>'),
        (None, '</div>'),
    ]},
    {"key": "demo", "title": "De publieke demo (verzonnen gegevens)", "demo": True, "body": []},
    {"key": "delen", "title": "Gelaagd delen", "body": [
        (None, '<div class="share">'),
        ("roles", '<div class="roles"><div class="role" data-at="roles"><b>Juridisch</b><span>namen · adressen · data</span></div>'
                  '<div class="role" data-at="roles" data-dt="0.5"><b>Communicatie</b><span>alleen organisaties</span></div>'
                  '<div class="role" data-at="roles" data-dt="1.0"><b>Iedereen</b><span>niets: alleen codes</span></div></div>'),
        ("redacted-pdf", '<div class="page" data-at="redacted-pdf"><div>Geachte <span class="bar">[PERSOON 1]</span>,</div>'
                         '<div>Naar aanleiding van uw verzoek van <span class="bar">[DATUM 1]</span></div>'
                         '<div>delen wij u mee dat <span class="bar">[ORGANISATIE 1]</span> het advies</div>'
                         '<div>heeft uitgebracht. Contact: <span class="bar">[TELEFOON 1]</span>.</div>'
                         '<div class="stamp" data-at="redacted-pdf" data-dt="2.0">opmaak blijft · waarden verwijderd</div></div>'),
        (None, '</div>'),
    ]},
    {"key": "autonomie", "title": "Data-autonomie", "body": [
        (None, '<div class="org">'),
        ("own-hardware", '<div class="org-label" data-at="own-hardware">Uw organisatie · eigen hardware</div>'),
        (None, '<div class="boxes">'),
        ("own-hardware", '<div class="box" data-at="own-hardware" data-dt="0.4">Inlezen &amp; zoeken</div>'
                         '<div class="box" data-at="own-hardware" data-dt="0.8">Lokale taalmodellen</div>'
                         '<div class="box" data-at="own-hardware" data-dt="1.2">Zoekindex (alleen codes)</div>'),
        ("key-vault", '<div class="box" data-at="key-vault">Eigen sleutelkluis</div>'),
        (None, '</div>'),
        ("own-hardware", '<div class="nocloud" data-at="own-hardware" data-dt="2.0">✕ geen cloud in het pad</div>'),
        (None, '</div>'),
    ]},
    {"key": "controle", "title": "Controleerbaar", "body": [
        (None, '<div class="chain">'),
        ("audit-chain", '<div class="blk" data-at="audit-chain"><b>ingelezen</b><span>#a41f…</span></div>'
                        '<div class="link" data-at="audit-chain" data-dt="0.6"></div><div class="blk" data-at="audit-chain" data-dt="0.9">'
                        '<b>gepseudonimiseerd</b><span>#7c02…</span></div><div class="link" data-at="audit-chain" data-dt="1.5"></div>'
                        '<div class="blk" data-at="audit-chain" data-dt="1.8"><b>onthuld</b><span>#13d8…</span></div>'),
        (None, '</div>'),
        (None, '<div class="badges">'),
        ("licence", '<span class="badge" data-at="licence">Open source · {licence}</span>'),
        ("nora", '<span class="badge" data-at="nora">Getoetst aan NORA</span>'),
        ("audit-chain", '<span class="badge" data-at="audit-chain" data-dt="2.5">Hash-geketend auditspoor</span>'),
        (None, '</div>'),
    ]},
    {"key": "bewijs", "title": "Bewijs: een pilot op een echte Woo-publicatie", "body": [
        (None, '<div class="stats">'),
        ("pilot-docs", '<div class="stat" data-at="pilot-docs"><b>{documents}</b><span>documenten ingelezen</span></div>'),
        ("pilot-redacted", '<div class="stat" data-at="pilot-redacted"><b>{box_maps}</b><span>met gelakte pdf</span></div>'),
        ("pilot-ranking", '<div class="stat" data-at="pilot-ranking"><b>{q_top2} / {q_total}</b><span>zoekvragen in de top 2</span></div>'),
        ("pilot-sample", '<div class="stat" data-at="pilot-sample"><b>{sample_clean} / {sample_n}</b><span>steekproef zonder achtergebleven persoonsgegeven</span></div>'),
        (None, '</div>'),
    ]},
    {"key": "contact", "title": "Meer weten", "body": [
        ("contact", '<div class="contact" data-at="contact">westerweel.work</div>'),
    ]},
]
