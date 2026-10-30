"""Build the film from resolved claims (tools/film/claims.py output):

    python tools/film/make.py <resolved.json> <outdir>   -> prints the mp4 path

Writes into <outdir>: wordsworth-uitleg.mp4, wordsworth-uitleg.srt, voice-over.md,
storyboard.md, and the intermediates (html/, audio/, mp4/, voice.wav)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pages  # noqa: E402
from assemble import assemble  # noqa: E402
from narration import narrate  # noqa: E402
from render import render  # noqa: E402

NAME = "wordsworth-uitleg.mp4"


def main(resolved_path, out):
    os.makedirs(out, exist_ok=True)
    scenes = pages.plan(json.load(open(resolved_path, encoding="utf-8")))
    timing = narrate(scenes, out)
    json.dump(timing, open(os.path.join(out, "timing.json"), "w"), indent=1)
    pages.write(scenes, timing, out)
    videos = render(scenes, timing, out)
    print(os.path.abspath(assemble(scenes, timing, videos, out, NAME)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
