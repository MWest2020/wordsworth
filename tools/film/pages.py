"""From the resolved claims to what gets rendered: the scene plan, one HTML page per
animated scene, the .srt, the voice-over script and the storyboard."""
import json
import os

from scenes import SCENES

HERE = os.path.dirname(os.path.abspath(__file__))


def plan(resolved):
    """Scenes with at least one proven claim: their captions (the claims' sentences in
    file order), which caption each claim starts at, and the values to fill in."""
    shown = [r for r in resolved if r["shown"]]
    out = []
    for sc in SCENES:
        mine = [r for r in shown if r["scene"] == sc["key"]]
        if not mine:
            continue
        captions, first, values = [], {}, {}
        for r in mine:
            first[r["id"]] = len(captions)
            captions += r["sentences"]
            values.update(r.get("values", {}))
        body = "".join(html for cid, html in sc["body"] if cid is None or cid in first)
        out.append({**sc, "captions": captions, "first": first,
                    "html": body.format(**values) if body else ""})
    return out


PAGE = """<!doctype html><html lang="nl"><head><meta charset="utf-8"><title>{title}</title>
<style>{css}</style></head><body>
<div class="top"><div class="brand">words<i>worth</i></div><div class="scene-n">{n} / {total}</div></div>
<h1>{title}</h1><div class="stage">{body}</div><div class="cap"><span id="cap"></span></div>
<script>
const CAPS = {caps}, STARTS = {starts}, CLAIM_T = {claim_t}, FADE = 0.7;
const cap = document.getElementById('cap');
// Every element tied to a claim appears when that claim is spoken (data-at: fades in;
// data-swap: switches state, e.g. value -> code); one whose claim is not in this film
// has no time and never appears.
const when = n => {{
  const t0 = CLAIM_T[n.dataset.at || n.dataset.swap];
  return t0 === undefined ? Infinity : t0 + parseFloat(n.dataset.dt || '0');
}};
const FADES = [...document.querySelectorAll('[data-at]')].map(n => {{
  n.classList.add('hide'); n.style.transition = 'none'; return [n, when(n)];
}});
const SWAPS = [...document.querySelectorAll('[data-swap]')].map(n => [n, when(n)]);
// Virtual time: the renderer calls __at(t) per frame and takes a screenshot.
window.__at = function(t){{
  let c = '';
  STARTS.forEach((st, i) => {{ if (t >= st) c = CAPS[i]; }});
  cap.textContent = c;
  FADES.forEach(([n, ts]) => {{
    const p = Math.max(0, Math.min(1, (t - ts) / FADE));
    n.classList.toggle('on', t >= ts);
    n.style.setProperty('opacity', String(p), 'important');
    n.style.setProperty('transform', 'translateY(' + ((1 - p) * 14) + 'px)', 'important');
  }});
  SWAPS.forEach(([n, ts]) => n.classList.toggle('on', t >= ts));
}};
</script></body></html>"""


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write(scenes, timing, out):
    css = open(os.path.join(HERE, "film.css"), encoding="utf-8").read()
    os.makedirs(os.path.join(out, "html"), exist_ok=True)
    total = len(scenes)
    for n, sc in enumerate(scenes, 1):
        if sc.get("demo"):
            continue
        st = timing[sc["key"]]["starts"]
        claim_t = {cid: st[i] for cid, i in sc["first"].items()}
        html = PAGE.format(title=sc["title"], css=css, n=n, total=total, body=sc["html"],
                           caps=json.dumps(sc["captions"], ensure_ascii=False),
                           starts=json.dumps(st), claim_t=json.dumps(claim_t))
        open(os.path.join(out, "html", sc["key"] + ".html"), "w", encoding="utf-8").write(html)
    srt, t, k = [], 0.0, 1
    vo = ["# Voice-over", "", "Gegenereerd uit de bewezen claims (docs/reference/film-claims.yml); "
          "elke alinea hoort bij één scène.", ""]
    sb = ["# Storyboard", ""]
    for n, sc in enumerate(scenes, 1):
        tm = timing[sc["key"]]
        for i, c in enumerate(sc["captions"]):
            a = t + tm["starts"][i]
            srt.append(f"{k}\n{srt_time(a)} --> {srt_time(a + tm['lens'][i] + 0.35)}\n{c}\n")
            k += 1
        sb.append(f"## {n}. {sc['title']} ({srt_time(t)[:8]}, {tm['duration']:.0f} s)")
        sb += ["", *[f"- {c}" for c in sc["captions"]], ""]
        vo += [f"**{n}. {sc['title']}**", "", " ".join(sc["captions"]), ""]
        t += tm["duration"]
    open(os.path.join(out, "wordsworth-uitleg.srt"), "w", encoding="utf-8").write("\n".join(srt))
    open(os.path.join(out, "voice-over.md"), "w", encoding="utf-8").write("\n".join(vo))
    open(os.path.join(out, "storyboard.md"), "w", encoding="utf-8").write("\n".join(sb))
    return t
