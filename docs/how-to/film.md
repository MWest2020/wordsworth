---
status: current
last_reviewed: 2026-10-30
---

# The explainer film: proof-gated, rebuilt daily

The film (Dutch, with a synthetic voice) says only what is proven on the day it is
built. Every sentence belongs to a claim in
[`docs/reference/film-claims.yml`](../reference/film-claims.yml), and every claim has a
check. A claim whose check fails today is left out of the film, and so is the picture
that goes with it. Every number in a sentence comes from a check's output. None is typed
into the file.

## Build it

```sh
WORDSWORTH_TEST_DATABASE_URL=postgresql+psycopg://wordsworth:wordsworth@127.0.0.1/wordsworth_test \
  tools/film/build.sh <outdir>
```

What it does:

1. It runs every check and writes the resolved claims: the shown claims with their
   filled sentences, and the dropped claims with the reason.
2. It compares the result with `<outdir>/claims.json` from the last build. If the film
   would say the same thing, it prints `unchanged` and stops. A drop reason worded
   differently does not count as a change.
3. Otherwise it narrates, renders and assembles the film. It prints the path of the
   mp4, and only then writes `claims.json`, so a build that failed is tried again on
   the next run.

What lands in `<outdir>`:

- `wordsworth-uitleg.mp4`: 1080p H.264 and AAC, loudness −16 LUFS.
- `wordsworth-uitleg.srt`.
- `voice-over.md` and `storyboard.md`.
- The intermediates: `html/`, `audio/`, `mp4/`, `voice.wav`, `timing.json`.

To rebuild after changing a scene's look but not its claims, delete
`<outdir>/claims.json`.

Run the checks on their own with
`uv run python tools/film/claims.py /tmp/claims.json`. It prints `shown` or `DROPPED`
for every claim, with the reason.

## What the checks need

Each kind of check needs something different. If what it needs is missing, its claims
drop.

- **pytest** checks need the integration tests to *pass*. A skipped test counts as not
  proven. So the test database has to be there (`WORDSWORTH_TEST_DATABASE_URL`), along
  with OpenSearch.
- **facts** checks need the live probe. It is
  [`tools/film/live_facts.py`](../../tools/film/live_facts.py), piped into the API pod
  (`ssh jumpy kubectl … exec -i deploy/wordsworth-api -- python -`). It prints counts
  and yes/no flags only. If the probe fails, every facts claim drops.
- **cmd** checks run from the repo root:
  - `licence_check.py` compares GitHub's licence, `LICENSE` and the SPDX headers.
  - `pilot_facts.py` reads the numbers from the pilot report.
  - `curl` fetches the public demo and the contact page.

The build tools come from `uv run --with` with pinned versions: piper-tts, Playwright
and imageio-ffmpeg. Set `FILM_CHROME` to use a Chromium other than the one Playwright
installed.

## The voice

The voice is Piper `nl_NL-alex-medium` (dataset licence CC0), offline. It is not in
git. [`narration.py`](../../tools/film/narration.py) downloads it once into
`${XDG_CACHE_HOME:-~/.cache}/wordsworth-film/voice/` and refuses any file whose sha256
differs from the pinned one. `SPOKEN` in that file maps what the screen shows to what
the voice says, for example `pdf` → "pee dee ef".

## Add or change a claim

1. In `film-claims.yml`, give the claim an `id`, a `scene`, the `sentences`, and at
   least one check: `facts`, `pytest`, `cmd` or `requires`. A number in a sentence is
   `{name}`, and the name must come from the check's output: a probe key, or a
   `key=value` line from the command. If the value is missing, the claim drops; nothing
   is guessed.
2. If the claim needs a picture, add a fragment to its scene in
   [`scenes.py`](../../tools/film/scenes.py), tagged with the claim. Elements with
   `data-at="<id>"` fade in when the claim is spoken (offset by `data-dt` seconds).
   Elements with `data-swap` switch state instead, for example from value to code.
3. A new number from the live system goes into `live_facts.py`. It must be a count,
   never a value.
4. `uv run pytest tests/test_film_claims.py` checks that every claim has a check and a
   known scene.

Never add a claim for something that is still being built. It goes in once a check
proves it.

## How it renders

The animated scenes render in virtual time. Each frame, the page is set to time *t*
(`window.__at`) and a screenshot is taken, so picture and voice stay in sync on any
machine. The demo scene runs on the live public demo, which uses made-up data, in real
time: every screenshot keeps its measured timestamp, and the video gives each frame its
real duration. The real length of each voice clip sets the caption times, the animation
times and the scene lengths.
