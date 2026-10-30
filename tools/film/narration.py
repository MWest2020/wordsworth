"""The Dutch voice-over: Piper (local, offline) speaks every caption; the real clip
lengths set the timing of captions, animations and scenes.

The voice model is not in git: it is downloaded once into a cache directory and checked
against the pinned sha256 below (dataset licence CC0)."""
import hashlib
import os
import re
import urllib.request
import wave

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_NL/alex/medium/"
VOICE = {
    "nl_NL-alex-medium.onnx": "22f0497c4d895a09fbc6a469459aa8954ea0955d3c6e19dbcc2e23acbb93e30b",
    "nl_NL-alex-medium.onnx.json": "9ea643871742c038511b6aaf20e6fc098a78a11968122d2f6ca3e50403423f95",
}
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                     "wordsworth-film", "voice")
LEAD = 0.5      # silence before a scene's first caption (the title settles)
GAP = 0.45      # pause between two captions
TAIL = 0.8      # pad after a scene's last caption

# What the screen shows vs. what the voice should say.
SPOKEN = [
    (r"BSN's", "burgerservicenummers"),
    (r"\bpdf\b", "pee dee ef"),
    (r"\bPDF\b", "pee dee ef"),
    (r"\bAPI\b", "aa pee ie"),
    (r"\bEUPL\b", "E U P L"),
    (r"\bMIT\b", "em ie tee"),
    (r"\bNORA\b", "Nora"),
    (r"westerweel\.work", "westerweel punt work"),
    (r"vóórdat", "voordat"),
    (r"\bén\b", "en"),
]


def spoken(text):
    for pat, rep in SPOKEN:
        text = re.sub(pat, rep, text)
    return text


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch_voice(cache=CACHE):
    """The model's path; downloads what is missing, refuses a file with the wrong hash."""
    os.makedirs(cache, exist_ok=True)
    for name, want in VOICE.items():
        path = os.path.join(cache, name)
        if not os.path.exists(path) or sha256(path) != want:
            tmp = path + ".part"
            urllib.request.urlretrieve(BASE + name, tmp)
            got = sha256(tmp)
            if got != want:
                os.remove(tmp)
                raise SystemExit(f"voice {name}: sha256 {got}, pinned {want}")
            os.replace(tmp, path)
    return os.path.join(cache, "nl_NL-alex-medium.onnx")


def narrate(scenes, out):
    """audio/<scene>-<i>.wav per caption; returns {scene: {starts, lens, duration}}."""
    from piper import PiperVoice, SynthesisConfig

    voice = PiperVoice.load(fetch_voice())
    cfg = SynthesisConfig(length_scale=1.08)   # a touch slower: calm, clear
    os.makedirs(os.path.join(out, "audio"), exist_ok=True)
    timing = {}
    for sc in scenes:
        starts, lens, t = [], [], LEAD
        for i, cap in enumerate(sc["captions"]):
            path = os.path.join(out, "audio", f"{sc['key']}-{i}.wav")
            with wave.open(path, "wb") as wf:
                voice.synthesize_wav(spoken(cap), wf, syn_config=cfg)
            with wave.open(path, "rb") as wf:
                d = wf.getnframes() / wf.getframerate()
            starts.append(round(t, 3))
            lens.append(round(d, 3))
            t += d + GAP
        timing[sc["key"]] = {"starts": starts, "lens": lens, "duration": round(t - GAP + TAIL, 3)}
    return timing
