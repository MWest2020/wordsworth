"""Render every scene as exact frames, so picture and voice stay in sync.

Animated scenes: virtual time. Per frame the page is set to time t (window.__at) and
screenshotted: smooth and exact on any machine. The demo scene is the live public demo
(made-up data), so real time: screenshots taken while the actions run, each with its
measured timestamp; the video gives each frame its real duration."""
import os
import shutil
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

DEMO = "https://mwest2020.github.io/wordsworth-demo/"
SIZE = {"width": 1920, "height": 1080}
FPS = 25
# The browser: FILM_CHROME, else whatever Playwright installed.
EXE = os.environ.get("FILM_CHROME") or None

OVERLAY = """
([caps, starts]) => {
  const d = document.createElement('div');
  d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;height:170px;background:#13213c;color:#fff;' +
    'display:flex;align-items:center;justify-content:center;padding:0 140px;text-align:center;' +
    'font:500 44px/1.25 "Helvetica Neue",Arial,"Liberation Sans",sans-serif;z-index:99999;zoom:1';
  const s = document.createElement('span'); d.appendChild(s);
  const tag = document.createElement('div');
  tag.textContent = 'Publieke demo · verzonnen gegevens';
  tag.style.cssText = 'position:fixed;right:40px;top:30px;background:#b5891e;color:#fff;padding:10px 22px;' +
    'border-radius:6px;font:700 26px Arial,sans-serif;z-index:99999';
  document.documentElement.appendChild(d); document.documentElement.appendChild(tag);
  caps.forEach((c, i) => setTimeout(() => { s.textContent = c; }, starts[i] * 1000));
}
"""


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(frames_dir, dst, duration, stamps=None):
    """CFR from numbered frames, or (stamps = [(file, t)]) each frame until the next."""
    ff = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"]
    if stamps is None:
        src = ["-framerate", str(FPS), "-i", os.path.join(frames_dir, "%05d.jpg")]
    else:
        lst = os.path.join(frames_dir, "list.txt")
        with open(lst, "w") as fh:
            for k, (f, t) in enumerate(stamps):
                nxt = stamps[k + 1][1] if k + 1 < len(stamps) else duration
                fh.write(f"file '{f}'\nduration {max(nxt - t, 0.001):.4f}\n")
            fh.write(f"file '{stamps[-1][0]}'\n")
        src = ["-f", "concat", "-safe", "0", "-i", lst]
    subprocess.run(ff + src + ["-vf", "fps=30,format=yuv420p", "-t", f"{duration:.3f}",
                               "-c:v", "libx264", "-preset", "medium", "-crf", "21", dst], check=True)


def scroll_to(page, selector, offset=-140):
    page.evaluate("""([sel, off]) => { const e = document.querySelector(sel) ||
        [...document.querySelectorAll('h2,h3')].find(h => h.textContent.includes(sel));
        if (!e) return; const z = parseFloat(document.body.style.zoom || 1);
        const y = e.getBoundingClientRect().top * z + window.scrollY + off;
        window.scrollTo({top: y, behavior: 'smooth'}); }""", [selector, offset])


def virtual(page, html, frames_dir, d):
    page.goto("file://" + html)
    page.wait_for_timeout(400)                       # fonts and layout settle
    for k in range(int(round(d * FPS))):
        page.evaluate(f"window.__at({k / FPS:.4f})")
        page.screenshot(path=os.path.join(frames_dir, f"{k:05d}.jpg"), type="jpeg", quality=90)


def demo(page, captions, st, d, frames_dir):
    """The five demo captions, in film-claims.yml order: intro, search, a document with
    codes only, reveal per department, the audit trail."""
    page.goto(DEMO, wait_until="networkidle")
    page.evaluate("document.body.style.zoom='1.45'")
    page.wait_for_timeout(400)
    stamps, go = [], time.monotonic()
    page.evaluate(OVERLAY, [captions, st])

    def shoot():
        f = os.path.join(frames_dir, f"{len(stamps):05d}.jpg")
        t = time.monotonic() - go
        page.screenshot(path=f, type="jpeg", quality=90)
        stamps.append((f, t))

    def until(t):
        while time.monotonic() - go < t:
            shoot()

    until(st[1])
    scroll_to(page, "#q", -260)
    for _ in range(4):
        shoot()
    for ch in "noodopvang":
        page.locator("#q").type(ch)
        shoot()
    until(st[2])
    scroll_to(page, "Reveal per afdeling", -40)
    until(st[3])
    page.locator("button.dept", has_text="Juridisch").click()
    until(st[3] + 2.4)
    page.locator("button.dept", has_text="Sales").click()
    until(st[4])
    page.evaluate("window.scrollBy({top: 260, behavior: 'smooth'})")
    until(d)
    return stamps


def render(scenes, timing, out):
    """mp4/<scene>.mp4 for every scene; returns their paths in order."""
    os.makedirs(os.path.join(out, "mp4"), exist_ok=True)
    paths = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=EXE)
        for sc in scenes:
            key, tm = sc["key"], timing[sc["key"]]
            fd = os.path.join(out, "frames", key)
            shutil.rmtree(fd, ignore_errors=True)
            os.makedirs(fd)
            page = b.new_page(viewport=SIZE)
            dst = os.path.join(out, "mp4", key + ".mp4")
            if sc.get("demo"):
                encode(fd, dst, tm["duration"], demo(page, sc["captions"], tm["starts"], tm["duration"], fd))
            else:
                virtual(page, os.path.join(out, "html", key + ".html"), fd, tm["duration"])
                encode(fd, dst, tm["duration"])
            page.close()
            shutil.rmtree(fd)
            paths.append(dst)
            print("rendered", key, f"{tm['duration']:.1f}s", file=sys.stderr, flush=True)
        b.close()
    return paths
