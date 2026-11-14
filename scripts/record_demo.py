"""Record the Blink demo path in a real browser: a backup video for the pitch, plus a GIF.

Drives the live site (real data, nothing staged), captures it in real time, and writes
    docs/media/blink-demo.mp4   full demo path with captions (backup recording)
    docs/media/blink-demo.gif   the Barnard's Star part, small enough for the README

Every object on the path must be warm first, or the video shows loading spinners:
    python scripts/warm_cache.py barnards-star orion

Setup (dev only, not needed to run Blink):
    pip install playwright imageio imageio-ffmpeg pillow
    python -m playwright install chromium

Usage:  python -m uvicorn api.main:app --port 8000      # in another terminal
        python scripts/record_demo.py [http://localhost:8000]
"""

import io
import sys
import time
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media"
BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
SIZE = {"width": 1280, "height": 800}
FPS = 10  # video frame rate; capture runs as fast as screenshots allow
GIF_WIDTH, GIF_FPS = 640, 6
SLOW = 600_000  # ms: a cold object can take minutes, so waits are generous

frames: list[tuple[float, bytes, bool]] = []  # (time, jpeg, part of the GIF?)
t_start = 0.0
paused = 0.0  # seconds spent waiting off camera: cut from the video's clock
in_gif = False

CAPTION_JS = """(t) => {
  let c = document.getElementById("demo-caption");
  if (!c) {
    c = document.createElement("div");
    c.id = "demo-caption";
    Object.assign(c.style, {
      position: "fixed", left: "50%", top: "124px", transform: "translateX(-50%)", zIndex: 99,
      background: "rgba(124,196,255,0.96)", color: "#021624", padding: "9px 18px",
      borderRadius: "999px", font: "600 17px system-ui, sans-serif", pointerEvents: "none",
      boxShadow: "0 10px 30px rgba(0,0,0,0.55)", whiteSpace: "nowrap",
    });
    document.body.append(c);
  }
  c.textContent = t;
  c.style.display = t ? "block" : "none";
}"""


def snap(page: Page) -> None:
    frames.append(
        (time.time() - t_start - paused, page.screenshot(type="jpeg", quality=85), in_gif)
    )


class OffCamera:
    """Waits inside this block don't appear in the video (no frozen frames)."""

    def __enter__(self) -> None:
        self.t0 = time.time()

    def __exit__(self, *exc: object) -> None:
        global paused
        paused += time.time() - self.t0


def hold(page: Page, seconds: float) -> None:
    """Keep capturing while the page does its thing (animations run in real time)."""
    end = time.time() + seconds
    while time.time() < end:
        snap(page)
        time.sleep(max(0.0, 1 / FPS - 0.02))


def caption(page: Page, text: str) -> None:
    page.evaluate(CAPTION_JS, text)


def ready(page: Page) -> None:
    """Wait (without recording) until the viewer has finished loading."""
    with OffCamera():
        page.wait_for_timeout(300)
        page.wait_for_selector("#msg", state="hidden", timeout=SLOW)
        page.wait_for_timeout(500)


def search(page: Page, text: str) -> None:
    page.click("#search-input")
    for ch in text:
        page.keyboard.type(ch)
        hold(page, 0.12)
    hold(page, 0.8)
    page.keyboard.press("Enter")


def view(page: Page, name: str) -> None:
    page.click(f'.views [data-view="{name}"]')


def record(page: Page) -> None:
    global t_start, in_gif
    page.goto(BASE + "/")
    page.wait_for_selector(".card")
    t_start = time.time()

    caption(page, "Blink: every visit NASA's SPHEREx made to the same patch of sky")
    hold(page, 3)

    caption(page, "Search any object")
    search(page, "Barnard")
    ready(page)

    in_gif = True
    caption(page, "Barnard's Star: each SPHEREx visit, on its real date")
    hold(page, 1.5)
    page.click("#play")
    hold(page, 6)
    page.click("#play")

    caption(page, "Blink between two visits: the star jumps")
    view(page, "blink")
    hold(page, 4.5)

    caption(page, "Difference: dark where it was, bright where it is now")
    view(page, "diff")
    ready(page)
    hold(page, 3.5)

    caption(page, "Colour-time: one visit per colour, so motion leaves a trail")
    view(page, "rgb")
    ready(page)
    hold(page, 3.5)
    in_gif = False

    # The star's spectrum uses its own cutouts. If they aren't warm, skip this step rather
    # than record a spinner (the wait itself isn't recorded).
    page.click('[data-tab="spectrum"]')
    try:
        with OffCamera():
            page.wait_for_selector("#spec-loading", state="hidden", timeout=15_000)
    except PlaywrightTimeout:
        print("Barnard's Star spectrum not warm: step skipped (run warm_cache.py barnards-star)")
    else:
        caption(page, "Spectrum: what it's made of, with every caveat shown")
        hold(page, 4)
        page.mouse.wheel(0, 500)
        hold(page, 3)

    caption(page, "Nebulae too: the Orion Nebula across a year")
    search(page, "Orion")
    ready(page)
    page.click('[data-tab="explore"]')
    hold(page, 1)
    page.click("#play")
    hold(page, 5.5)
    page.click("#play")

    caption(page, "Its spectrum: glowing hydrogen lines, measured by SPHEREx")
    page.click('[data-tab="spectrum"]')
    with OffCamera():
        page.wait_for_selector("#spec-loading", state="hidden", timeout=SLOW)
    hold(page, 4)

    caption(page, "Blink: real NASA data, real dates, nothing made up")
    page.click('[data-tab="explore"]')
    hold(page, 3)


def resample(items: list[tuple[float, bytes, bool]], fps: int) -> list[bytes]:
    """Constant frame rate from irregular captures: show the latest frame at each tick."""
    if not items:
        return []
    out, i = [], 0
    t0, t_end = items[0][0], items[-1][0]
    for k in range(int((t_end - t0) * fps) + 1):
        t = t0 + k / fps
        while i + 1 < len(items) and items[i + 1][0] <= t:
            i += 1
        out.append(items[i][1])
    return out


def write_outputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    video = OUT / "blink-demo.mp4"
    with imageio.get_writer(video, fps=FPS, codec="libx264", quality=7, pixelformat="yuv420p") as w:
        for jpg in resample(frames, FPS):
            w.append_data(np.asarray(Image.open(io.BytesIO(jpg)).convert("RGB")))
    print(f"wrote {video.relative_to(ROOT)} ({video.stat().st_size / 1e6:.1f} MB)")

    gif_frames = []
    for jpg in resample([f for f in frames if f[2]], GIF_FPS):
        im = Image.open(io.BytesIO(jpg)).convert("RGB")
        im = im.resize((GIF_WIDTH, round(im.height * GIF_WIDTH / im.width)), Image.LANCZOS)
        gif_frames.append(im.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE))
    gif = OUT / "blink-demo.gif"
    if gif_frames:
        gif_frames[0].save(
            gif,
            save_all=True,
            append_images=gif_frames[1:],
            duration=1000 // GIF_FPS,
            loop=0,
            optimize=True,
        )
        print(f"wrote {gif.relative_to(ROOT)} ({gif.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=SIZE, device_scale_factor=1)
        record(page)
        browser.close()
    print(f"captured {len(frames)} frames over {frames[-1][0]:.0f} s")
    write_outputs()


if __name__ == "__main__":
    main()
