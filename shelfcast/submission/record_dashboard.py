"""Record the product shots of the demo video (storyboard shots 3, 5, 6 and 7) from the dashboard.

    python submission/record_dashboard.py --url https://yy5652-hash.github.io/shelfcast/ --out submission/video

Drives the real dashboard (the static demo, whose answers were produced on the MI300X) in Playwright's
Chromium at 1920x1080 in the dark theme. Each shot isolates one subject on the page, as the
storyboard asks: everything else is hidden and the subject is centred with a slow push-in. Nothing on
screen is drawn by this script; it only hides, centres and clicks. Writes shot_03.mp4 ... shot_07.mp4.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

STAGE_CSS = """
#stage { position: fixed; inset: 0; z-index: 50; background: #0f1216; display: flex; align-items: center;
  justify-content: center; }
#stage > .inner { animation: push var(--dur) linear both; }
@keyframes push { from { transform: scale(var(--k)); } to { transform: scale(calc(var(--k) * 1.03)); } }
#stage .tile { background: #171b21; }
"""

SETUP = """async ([title, holiday]) => {
  const s = SKUS.find((x) => x.title.startsWith(title));
  document.getElementById("sku").value = s.sku_id;
  document.getElementById("sku").dispatchEvent(new Event("change"));
  const w = s.weeks.find((x) => x.label.includes(holiday));
  document.getElementById("week").value = String(w.index);
}"""

# Moves one element onto a full-screen stage, centred, with a slow push-in. (Hiding the rest of the
# page with visibility rules instead looks right in screenshots but records blank frames.)
FOCUS = """([sel, k, dur, width]) => {
  let st = document.getElementById("stage");
  if (!st) { st = document.createElement("div"); st.id = "stage"; document.body.append(st); }
  const inner = document.createElement("div");
  inner.className = "inner";
  inner.style.setProperty("--k", k); inner.style.setProperty("--dur", dur + "s");
  const e = document.querySelector(sel);
  if (width) e.style.width = width + "px";
  inner.append(e);
  st.replaceChildren(inner);
  // A moved canvas loses its drawing until Chart.js redraws it.
  if (e.querySelector("canvas") && typeof chart !== "undefined" && chart) { chart.resize(); chart.update("none"); }
}"""

BIG_CHART = """() => {
  const w = document.querySelector(".chart-wrap");
  w.style.width = "1500px"; w.style.height = "720px";
  chart.options.scales.x.ticks.font = { size: 18 }; chart.options.scales.y.ticks.font = { size: 18 };
  chart.resize(); chart.update("none");
}"""

SHOW_AGENT = """(visible) => {
  chart.data.datasets.forEach((d, i) => { if (d.label.startsWith("ShelfCast")) chart.setDatasetVisibility(i, visible); });
  chart.options.animation = visible ? { duration: 1100, easing: "easeOutCubic" } : false;
  chart.update();
}"""

COUNT_UP = """([from, to, ms]) => new Promise((done) => {
  const v = document.querySelector(".tile.accent .v"), t0 = performance.now();
  const step = (now) => {
    const p = Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - p, 3);
    v.textContent = `${Math.round(from + (to - from) * e)} units`;
    if (p < 1) requestAnimationFrame(step); else done();
  };
  v.textContent = `${from} units`; requestAnimationFrame(step);
})"""


def stage_appears(webm: Path, ffmpeg: str, fps: int = 10) -> float:
    raw = subprocess.run([ffmpeg, "-loglevel", "error", "-i", str(webm), "-vf", f"fps={fps},scale=192:108",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, 108 * 192).astype(int)
    jumps = np.abs(np.diff(frames, axis=0)).sum(axis=1)
    first = int(np.argmax(jumps > 0.5 * jumps.max()))
    return (first + 1 + 0.5) / fps


def shot(browser, url: str, out: Path, ffmpeg: str, n: int, script) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, color_scheme="dark",
                                  record_video_dir=tmp, record_video_size={"width": 1920, "height": 1080})
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_function("typeof SKUS !== 'undefined' && SKUS.length > 0")
        page.add_style_tag(content=STAGE_CSS)
        # The page runs one forecast on load; let it finish so it cannot replace the shot's elements.
        page.wait_for_selector(".tile.accent")
        page.evaluate(SETUP, ["Canned Pumpkin", "Thanksgiving"])
        page.click("#go")
        page.wait_for_timeout(800)
        page.wait_for_function("!document.getElementById('go').disabled")
        page.evaluate(BIG_CHART)
        script(page)
        ctx.close()
        webm = Path(page.video.path())
        shutil.copy(webm, out / f"raw_{n:02d}.webm")
        target = out / f"shot_{n:02d}.mp4"
        # Wall-clock times do not map onto the recording's timeline, so the clip starts where the
        # stage first appears on screen (the largest jump between frames) and runs to the end.
        start = stage_appears(webm, ffmpeg)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(webm),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-crf", "16", str(target)], check=True)
    return target


def shot3(page):
    """The system forecast alone: history and the grey baseline bar for Thanksgiving week."""
    page.evaluate(SHOW_AGENT, False)
    page.evaluate(FOCUS, [".chart-wrap", 1.0, 16, 1500])
    page.wait_for_timeout(300)
    page.wait_for_timeout(16000)


def shot5(page):
    """The teal bar rises beside the grey one, then the order tile counts from 21 to 40."""
    page.evaluate(SHOW_AGENT, False)
    page.evaluate(FOCUS, [".chart-wrap", 1.0, 9, 1500])
    page.wait_for_timeout(1800)
    page.evaluate(SHOW_AGENT, True)
    page.wait_for_timeout(7000)
    final = int(page.text_content(".tile.accent .v").split()[0])
    base = int(page.text_content(".tiles .tile:nth-child(2) .v").split()[0])
    page.evaluate(FOCUS, [".tile.accent", 3.2, 11, 420])
    page.evaluate(COUNT_UP, [base, final, 1400])
    page.wait_for_timeout(9500)


def shot6(page):
    """The driver row with its evidence."""
    page.evaluate(FOCUS, ["ul.drivers", 1.8, 10, 1000])
    page.wait_for_timeout(300)
    page.wait_for_timeout(10000)


def shot7(page):
    """A planner note is typed; the order drops."""
    page.evaluate(FOCUS, [".card", 1.5, 8, 420])
    page.wait_for_timeout(300)
    page.wait_for_timeout(800)
    page.click("#notes")
    page.keyboard.type("Store closed Monday for renovation", delay=65)
    page.wait_for_timeout(900)
    page.click("#go")
    page.wait_for_function("document.querySelector('.tile.accent .v') && !document.getElementById('go').disabled")
    page.wait_for_timeout(200)
    page.evaluate(FOCUS, [".tile.accent", 3.2, 7, 420])
    page.wait_for_timeout(6000)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="https://yy5652-hash.github.io/shelfcast/")
    ap.add_argument("--out", default="submission/video")
    ap.add_argument("--only", type=int, nargs="*")
    args = ap.parse_args()

    import imageio_ffmpeg
    from playwright.sync_api import sync_playwright

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shots = {3: shot3, 5: shot5, 6: shot6, 7: shot7}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for n, fn in shots.items():
            if not args.only or n in args.only:
                print("wrote", shot(browser, args.url, out, imageio_ffmpeg.get_ffmpeg_exe(), n, fn))
        browser.close()


if __name__ == "__main__":
    main()
