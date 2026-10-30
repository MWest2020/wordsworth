"""Join the scene videos, lay the voice clips out on one track at their caption starts,
and mux both into one mp4 (H.264 1080p + AAC, loudness -16 LUFS)."""
import array
import os
import subprocess
import wave

from render import ffmpeg

FPS = 30


def run(args):
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"] + args, check=True)


def voice_track(scenes, timing, out):
    """One mono track: every clip at its scene start + caption start. Scene starts are
    the sum of the video lengths, rounded to whole frames like the encode."""
    rate, clips, pos = None, [], 0.0
    for sc in scenes:
        tm = timing[sc["key"]]
        for i, st in enumerate(tm["starts"]):
            with wave.open(os.path.join(out, "audio", f"{sc['key']}-{i}.wav"), "rb") as wf:
                rate = rate or wf.getframerate()
                clips.append((pos + st, array.array("h", wf.readframes(wf.getnframes()))))
        pos += round(tm["duration"] * FPS) / FPS
    track = array.array("h", bytes(2 * (int(pos * rate) + rate)))
    for at, pcm in clips:
        i0 = int(at * rate)
        track[i0:i0 + len(pcm)] = pcm
    path = os.path.join(out, "voice.wav")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(track.tobytes())
    return path, pos


def assemble(scenes, timing, videos, out, name):
    lst = os.path.join(out, "concat.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{v}'\n" for v in videos)
    silent = os.path.join(out, "video-only.mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    voice, length = voice_track(scenes, timing, out)
    dst = os.path.join(out, name)
    run(["-i", silent, "-i", voice, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "128k",
         "-t", f"{length:.3f}", "-movflags", "+faststart", dst])
    os.remove(silent)
    os.remove(lst)
    return dst
