"""Build the pitch deck from the result files, so no number is typed by hand.

    python submission/build_deck.py --results results --out submission/deck

Writes deck.html and, when Google Chrome is installed, deck.pdf (16:9, one slide per page).
A slide whose numbers are missing says so instead of showing a guess.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
from pathlib import Path

CSS = """
@page { size: 1600px 900px; margin: 0 }
* { box-sizing: border-box }
html, body { margin: 0; background: #0f1216; color: #e8ebef;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact }
.slide { width: 1600px; height: 900px; padding: 90px 110px; position: relative; overflow: hidden;
  page-break-after: always; display: flex; flex-direction: column; justify-content: center }
.kicker { font-size: 22px; letter-spacing: .16em; text-transform: uppercase; color: #8c96a5; margin-bottom: 26px }
h1 { font-size: 104px; line-height: 1.02; margin: 0 0 28px; letter-spacing: -.03em; font-weight: 700 }
h2 { font-size: 64px; line-height: 1.08; margin: 0 0 34px; letter-spacing: -.02em; font-weight: 700; max-width: 1250px }
p, li { font-size: 32px; line-height: 1.4; color: #c5ccd6; max-width: 1180px; margin: 0 0 14px }
ul { margin: 0; padding-left: 1.1em }
b, .accent { color: #35c2a8 }
.muted { color: #8c96a5 }
.foot { position: absolute; left: 110px; right: 110px; bottom: 54px; font-size: 20px; color: #6f7a88;
  display: flex; justify-content: space-between }
.nums { display: grid; grid-template-columns: repeat(3, 1fr); gap: 40px; margin-top: 10px }
.num .v { font-size: 120px; font-weight: 700; letter-spacing: -.03em; line-height: 1; color: #35c2a8 }
.num .v.grey { color: #e8ebef }
.num .k { font-size: 26px; color: #c5ccd6; margin-top: 14px; line-height: 1.3 }
.num .s { font-size: 20px; color: #8c96a5; margin-top: 8px; line-height: 1.35 }
.flow { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-top: 8px }
.step { border: 1.5px solid #2a3038; border-radius: 14px; padding: 22px 20px; min-height: 210px }
.step.on { border-color: #35c2a8; background: rgba(53,194,168,.10) }
.step .n { font-size: 18px; color: #8c96a5; letter-spacing: .12em; text-transform: uppercase }
.step .t { font-size: 27px; font-weight: 700; margin: 10px 0 8px; line-height: 1.15 }
.step .d { font-size: 20px; color: #c5ccd6; line-height: 1.35 }
table { border-collapse: collapse; font-size: 26px; margin-top: 6px; font-variant-numeric: tabular-nums }
th, td { padding: 12px 26px 12px 0; text-align: right; border-bottom: 1px solid #2a3038 }
th:first-child, td:first-child { text-align: left; padding-right: 50px }
th { color: #8c96a5; font-weight: 500; font-size: 21px }
tr.hl td { color: #35c2a8; font-weight: 700 }
img.shot { max-width: 100%; max-height: 560px; border-radius: 12px; border: 1px solid #2a3038 }
.pending { color: #fb923c }
"""


def esc(x) -> str:
    return html.escape(str(x))


def signed(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x:+.{digits}f}%"


def load(results: Path):
    runs = []
    for p in sorted(results.glob("backtest_*.json")):
        try:
            runs.append(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    bench = None
    if (results / "bench.json").exists():
        bench = json.loads((results / "bench.json").read_text())
    by = {r["meta"]["dataset"]: r for r in runs}
    real = next((r for r in runs if r["meta"]["source"] != "synthetic"), None)
    synth = by.get("synthetic-store")
    notes = by.get("synthetic-store-notes")
    return real, synth, notes, bench


def num(value: str, label: str, small: str = "", grey: bool = False) -> str:
    return (f'<div class="num"><div class="v{" grey" if grey else ""}">{esc(value)}</div>'
            f'<div class="k">{esc(label)}</div><div class="s">{esc(small)}</div></div>')


def slide(body: str, foot: str = "") -> str:
    return (f'<section class="slide">{body}<div class="foot"><span>ShelfCast · AMD Developer Hackathon ACT III</span>'
            f'<span>{esc(foot)}</span></div></section>')


def pending(what: str) -> str:
    return f'<p class="pending">Not run yet: {esc(what)}. Run deploy/run_all.sh on the GPU host, then rebuild.</p>'


def build(results: Path, shot: Path | None, repo: str, demo: str) -> str:
    real, synth, notes, bench = load(results)
    slides = []

    slides.append(slide(
        '<div class="kicker">Reinvent Commerce</div><h1>ShelfCast</h1>'
        '<p style="font-size:40px;color:#e8ebef;max-width:1150px">An AI demand planner on an <b>AMD Instinct MI300X</b> '
        'that turns a forecast into the right order.</p>'
        f'<p class="muted" style="margin-top:36px">{esc(repo)}<br>{esc(demo)}</p>'))

    slides.append(slide(
        '<div class="kicker">The problem</div><h2>How many should we order?</h2>'
        '<ul><li>Every week, every store, every product. Too few is an empty shelf; too many is waste.</li>'
        '<li>Replenishment systems extrapolate last month. They cannot see a holiday, a promotion, '
        'or what the store manager knows.</li>'
        '<li>Planners patch the number by hand: slow, inconsistent, and never checked against what sold.</li></ul>'))

    if shot and shot.exists():
        slides.append(slide(
            '<div class="kicker">What the planner sees</div>'
            f'<img class="shot" src="{esc(shot.resolve().as_uri())}" alt="ShelfCast dashboard">'
            '<p style="margin-top:22px">One screen: the range, the order, each driver with its evidence, '
            'and the exact brief the model read.</p>'))

    slides.append(slide(
        '<div class="kicker">How it works</div><h2>A statistical forecast, then judgment, then a decision.</h2>'
        '<div class="flow">'
        '<div class="step"><div class="n">1</div><div class="t">Baseline</div><div class="d">Exponential smoothing with '
        'quantiles from its own past errors.</div></div>'
        '<div class="step"><div class="n">2</div><div class="t">Evidence</div><div class="d">Past event and promotion effects, '
        'kept only if they clear the product\'s own noise.</div></div>'
        '<div class="step on"><div class="n">3 · on AMD</div><div class="t">LLM judgment</div><div class="d">Reads the evidence '
        'and the planner\'s notes; returns a multiplier, two spreads, and reasons.</div></div>'
        '<div class="step"><div class="n">4</div><div class="t">Guard + calibration</div><div class="d">No evidence and no note: '
        'the baseline stands. Ranges recalibrated on past errors.</div></div>'
        '<div class="step"><div class="n">5</div><div class="t">Order</div><div class="d">The demand quantile where lost margin '
        'balances leftover cost.</div></div></div>'
        '<p class="muted" style="margin-top:30px;font-size:24px">The language model is never the only forecasting method.</p>'))

    if bench and bench.get("levels"):
        best = max(bench["levels"], key=lambda r: r["forecasts_per_min"])
        gpu = next((t for t in ("MI355X", "MI325X", "MI300X") if t in (bench.get("gpu_info") or "")), None)
        body = ('<div class="kicker">Built on AMD</div>'
                f'<h2>One {"AMD Instinct " + gpu if gpu else "GPU"}. Open weights. vLLM on ROCm.</h2><div class="nums">'
                + num(f"{best['forecasts_per_min']:,.0f}", "forecasts a minute",
                      f"{best['concurrency']} concurrent, {bench['n_samples']} samples each")
                + num(f"{best['output_tok_per_s']:,.0f}", "output tokens a second", f"p95 latency {best['p95_latency_s']:.1f}s", grey=True)
                + num(f"${best['usd_per_1k_forecasts']:.2f}", "per 1,000 forecasts",
                      f"at ${bench['price_per_hour']:.2f} per GPU-hour", grey=True)
                + f'</div><p style="margin-top:44px">Model <b>{esc(bench["model"])}</b>. Each brief is prefilled once for all '
                  'samples; guided decoding enforces the JSON. Sales data never leaves the retailer\'s GPU.</p>')
    else:
        body = '<div class="kicker">Built on AMD</div><h2>One AMD Instinct MI300X. Open weights. vLLM on ROCm.</h2>' + pending("the inference benchmark")
    slides.append(slide(body))

    if real:
        m, s = real["meta"], real["summary"]
        ev = real["segments"]["event_weeks"]
        body = ('<div class="kicker">Does it pay? Real Walmart sales (M5)</div>'
                f'<h2>{m["n_forecasts"]:,} forecasts, each made only from the past.</h2><div class="nums">'
                + num(signed(None if s.get("newsvendor_saving_pct") is None else -s["newsvendor_saving_pct"]),
                      "inventory cost", "ordering the cost-optimal quantile instead of the point forecast")
                + num(signed(s.get("fva_pinball_pct")), "forecast accuracy vs baseline",
                      f"pinball loss, positive is better; event weeks {signed(ev.get('fva_pinball_pct'))}", grey=True)
                + num(f"{100 * s['agent_cal']['coverage_90']:.0f}%", "of outcomes inside the 90% range", "target 90%", grey=True)
                + f'</div><p style="margin-top:44px" class="muted">{m["n_series"]} item-store series, {m["weeks"][0]} to '
                  f'{m["weeks"][-1]}, model {esc(real["llm"]["model"])}. These items are anonymised and carry no promotion '
                  'data, so there is little for judgment to add: the gain here is the decision layer.</p>')
    else:
        body = '<div class="kicker">Does it pay? Real Walmart sales (M5)</div><h2>Rolling backtest on real sales.</h2>' + pending("the M5 backtest")
    slides.append(slide(body))

    if synth or notes:
        cells = []
        if synth:
            ev = synth["segments"]["event_weeks"]
            cells.append(num(signed(None if ev.get("cost_saving_pct") is None else -ev["cost_saving_pct"]),
                             "inventory cost in holiday and promotion weeks", "synthetic store, vs calibrated baseline"))
        if notes and "noted_weeks" in notes["segments"]:
            nw = notes["segments"]["noted_weeks"]
            cells.append(num(signed(nw.get("fva_pinball_pct")), "forecast accuracy in weeks with a planner note",
                             "pinball loss vs calibrated baseline; positive is better"))
            cells.append(num(signed(nw.get("fva_vs_rule_pct")), "the same, vs a rule with no LLM",
                             "the baseline and the rule cannot read a note", grey=True))
        body = ('<div class="kicker">Where judgment earns its place</div>'
                '<h2>When there is something to read, the model reads it.</h2>'
                f'<div class="nums">{"".join(cells)}</div>'
                '<p style="margin-top:44px" class="muted">A generated store with holidays, promotions and free-text notes such as '
                '"supplier warns this week\'s delivery will be short" (no number given). Labelled synthetic throughout.</p>')
    else:
        body = '<div class="kicker">Where judgment earns its place</div><h2>Events, promotions and planner notes.</h2>' + pending("the synthetic backtests")
    slides.append(slide(body))

    slides.append(slide(
        '<div class="kicker">What we learned, and what is next</div><h2>We ran the ablations before the pitch.</h2>'
        '<ul><li>Left free, the model made forecasts <b>worse</b> on real data: it read routine calendar entries as events. '
        'So it is the judgment layer, tied to evidence by a guard.</li>'
        '<li>Its own contribution is measured apart from everything else, against a rule that uses the same evidence.</li>'
        '<li>Limits: one week ahead, no carry-over stock, assumed margins.</li>'
        '<li>Next: multi-week horizons, real promotion calendars, planner feedback as training data.</li></ul>'))

    slides.append(slide(
        '<div class="kicker">ShelfCast</div><h1 style="font-size:84px">From forecast to the right order.</h1>'
        f'<p style="font-size:34px">Open model. Your GPU. Your data stays home.</p><p class="muted">{esc(repo)}<br>{esc(demo)}</p>'))

    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ShelfCast pitch</title><style>{CSS}</style></head><body>{"".join(slides)}</body></html>'


def to_pdf(html_path: Path, pdf_path: Path) -> bool:
    mac = "Google Chrome.app/Contents/MacOS/Google Chrome"
    chrome = next((c for c in (f"/Applications/{mac}", str(Path.home() / "Applications" / mac),
                               shutil.which("google-chrome") or "", shutil.which("chromium") or "") if c and Path(c).exists()), None)
    if not chrome:
        return False
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()],
                   check=True, capture_output=True, timeout=120)
    return pdf_path.exists()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="submission/deck")
    ap.add_argument("--screenshot", default="submission/dashboard.png")
    ap.add_argument("--repo", default="github.com/yy5652-hash/shelfcast")
    ap.add_argument("--demo", default="demo URL: to be added")
    args = ap.parse_args()
    out = Path(args.out)
    page = build(Path(args.results), Path(args.screenshot), args.repo, args.demo)
    out.with_suffix(".html").write_text(page)
    made = to_pdf(out.with_suffix(".html"), out.with_suffix(".pdf"))
    print(f"wrote {out.with_suffix('.html')}" + (f" and {out.with_suffix('.pdf')}" if made else " (no Chrome found: PDF skipped)"))


if __name__ == "__main__":
    main()
