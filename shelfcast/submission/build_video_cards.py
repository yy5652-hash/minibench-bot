"""Render the type-on-black shots of the demo video (storyboard shots 1, 2, 4, 8-10, 12, 13).

    python submission/build_video_cards.py --results results --out submission/video

Each shot is a small HTML page with one subject and one slow push-in, recorded at 1920x1080 with
Playwright's bundled Chromium and written as shot_NN.mp4 (silent; voice and screen recordings are
added in the edit). Number shots take their figure from the result files and are skipped, with a
message, when that result does not exist: no shot is ever rendered with a placeholder number.

Needs: pip install playwright imageio-ffmpeg  (and `playwright install chromium` once).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:1920px;height:1080px;background:#0f1216;overflow:hidden;
  font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;color:#e8ebef}}
.stage{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
  animation:push {dur}s linear both}}
@keyframes push{{from{{transform:scale(1)}}to{{transform:scale(1.03)}}}}
@keyframes rise{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}
.line{{font-size:92px;font-weight:700;letter-spacing:-.02em;text-align:center;max-width:1500px;line-height:1.1;
  opacity:0;animation:rise .9s ease-out .5s both}}
.pair{{display:flex;gap:240px;margin-top:70px}}
.pair span{{font-size:56px;color:#8c96a5;opacity:0;animation:rise .8s ease-out both}}
.num{{font-size:300px;font-weight:700;letter-spacing:-.04em;line-height:1;color:#35c2a8;
  opacity:0;animation:rise .7s ease-out .6s both}}
.label{{font-size:44px;color:#c5ccd6;margin-top:36px;opacity:0;animation:rise .8s ease-out 1.4s both}}
.small{{font-size:30px;color:#8c96a5;margin-top:16px;opacity:0;animation:rise .8s ease-out 1.9s both}}
.caption{{position:absolute;left:96px;bottom:84px;font-size:34px;color:#8c96a5;opacity:0;animation:rise .8s ease-out 1.2s both}}
.brand{{font-size:150px;font-weight:700;letter-spacing:-.03em;opacity:0;animation:rise .9s ease-out .4s both}}
.url{{font-size:34px;color:#8c96a5;margin-top:34px;opacity:0;animation:rise .8s ease-out 1.6s both;text-align:center;line-height:1.5}}
</style></head><body><div class="stage">{body}</div>{caption}</body></html>"""


def signed(x: float) -> str:
    return f"{x:+.1f}%".replace("-", "−")


def shots(results: Path, repo: str, demo: str) -> list[dict]:
    def load(name: str):
        p = results / name
        return json.loads(p.read_text()) if p.exists() else None

    real = next((json.loads(p.read_text()) for p in sorted(results.glob("backtest_m5*.json"))), None)
    notes = load("backtest_synthetic-store-notes.json")
    out = [
        dict(n=1, dur=8, body='<div class="line">How many should we order?</div>'),
        dict(n=2, dur=10, body='<div class="line" style="animation-delay:0s">How many should we order?</div>'
                               '<div class="pair"><span style="animation-delay:1.2s">Too few.</span>'
                               '<span style="animation-delay:3.2s">Too many.</span></div>',
             caption="Empty shelf. Or waste."),
        dict(n=4, dur=4, body=""),  # the beat of silence before the order changes
    ]
    if real:
        s, m = real["summary"], real["meta"]
        if s.get("newsvendor_saving_pct") is not None:
            out.append(dict(n=8, dur=9, body=f'<div class="num">{signed(-s["newsvendor_saving_pct"])}</div>'
                                              '<div class="label">inventory cost on real Walmart sales</div>'
                                              '<div class="small">ordering the cost-optimal quantile, not the point forecast</div>',
                            caption=f'Real Walmart sales. {m["n_series"]} products. {m["config"]["n_origins"]} weeks.'))
    else:
        print("skipped shot 8: no M5 backtest in the results folder")
    if notes and "noted_weeks" in notes["segments"]:
        nw = notes["segments"]["noted_weeks"]
        if nw.get("cost_saving_pct") is not None:
            out.append(dict(n=9, dur=9, body=f'<div class="num">{signed(-nw["cost_saving_pct"])}</div>'
                                              '<div class="label">inventory cost when the planner left a note</div>'
                                              '<div class="small">synthetic store; the note names no number</div>',
                            caption="It reads what you know."))
        if nw.get("fva_vs_rule_pct") is not None:
            out.append(dict(n=10, dur=9, body=f'<div class="num">{signed(nw["fva_vs_rule_pct"])}</div>'
                                               '<div class="label">accuracy over a model with no LLM</div>'
                                               '<div class="small">same evidence, same weeks; only one of them can read</div>',
                            caption="Judgment, measured."))
    else:
        print("skipped shots 9-10: no planner-notes backtest in the results folder")
    out += [
        dict(n=12, dur=8, body='<div class="line">Your model. Your GPU. Your data.</div>'),
        dict(n=13, dur=8, body='<div class="brand">ShelfCast</div>'
                               f'<div class="url">{repo}<br>{demo}</div>', caption="From forecast to the right order."),
    ]
    return out


def render(shot: dict, out_dir: Path, browser, ffmpeg: str) -> Path:
    caption = f'<div class="caption">{shot["caption"]}</div>' if shot.get("caption") else ""
    with tempfile.TemporaryDirectory() as tmp:
        page_file = Path(tmp) / "shot.html"
        page_file.write_text(PAGE.format(dur=shot["dur"], body=shot["body"], caption=caption))
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
                                  record_video_dir=tmp, record_video_size={"width": 1920, "height": 1080})
        page = ctx.new_page()
        page.goto(page_file.as_uri())
        page.wait_for_timeout(int(shot["dur"] * 1000))
        ctx.close()
        webm = Path(page.video.path())
        target = out_dir / f"shot_{shot['n']:02d}.mp4"
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(webm), "-t", str(shot["dur"]),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-crf", "16", str(target)], check=True)
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="submission/video")
    ap.add_argument("--repo", default="github.com/yy5652-hash/minibench-bot")
    ap.add_argument("--demo", default="")
    ap.add_argument("--only", type=int, nargs="*", help="shot numbers to render")
    args = ap.parse_args()

    import imageio_ffmpeg
    from playwright.sync_api import sync_playwright

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [s for s in shots(Path(args.results), args.repo, args.demo) if not args.only or s["n"] in args.only]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for s in todo:
            print("wrote", render(s, out_dir, browser, imageio_ffmpeg.get_ffmpeg_exe()))
        browser.close()


if __name__ == "__main__":
    main()
