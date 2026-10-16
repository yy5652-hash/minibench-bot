"""Export the dashboard as a static site (GitHub Pages) that needs no server and no GPU.

    python submission/build_static_demo.py --dataset data/synthetic-store.json --results results \
        --cache results/llm_cache.sqlite --out site [--live]

Every API answer the page can ask for is written to a JSON file: info, SKUs, backtests, the
benchmark, and the forecast for every SKU and selectable week, plus each example planner note on
the upcoming weeks. With --live, forecasts missing from the cache are computed on the model
endpoint (run this on the GPU host); without it, misses fall back to the statistical baseline, as
replay mode does. The page gets a small fetch shim that reads those files and recomputes the order
for any margin and leftover cost in the browser, with the same newsvendor rule as the server.
Free-text notes other than the examples need the live server and say so.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelfcast.agent import ForecastAgent
from shelfcast.cli import _dataset, _llm
from shelfcast.server import WEB_DIR, create_app

SHIM = r"""<script>
// Static demo: answers come from pre-computed JSON files, orders are recomputed here.
(() => {
  const realFetch = window.fetch.bind(window);
  const NOTES = __NOTES__;
  const ok = (obj) => new Response(JSON.stringify(obj), { status: 200, headers: { "Content-Type": "application/json" } });
  const fail = (msg) => new Response(msg, { status: 400 });
  function quantileAt(q, p, lv) {
    if (p <= lv[0]) return Math.max(0, q[0] - (q[1] - q[0]) / (lv[1] - lv[0]) * (lv[0] - p));
    const n = lv.length;
    if (p >= lv[n - 1]) return q[n - 1] + (q[n - 1] - q[n - 2]) / (lv[n - 1] - lv[n - 2]) * (p - lv[n - 1]);
    for (let i = 1; i < n; i++) if (p <= lv[i]) return q[i - 1] + (q[i] - q[i - 1]) * (p - lv[i - 1]) / (lv[i] - lv[i - 1]);
  }
  const r2 = (x) => Math.round(x * 100) / 100, r3 = (x) => Math.round(x * 1000) / 1000;
  function pinball(y, q, lv) { return q.reduce((a, qi, i) => a + Math.max(lv[i] * (y - qi), (lv[i] - 1) * (y - qi)), 0) / q.length; }
  function decide(r, margin, overage) {
    const lv = r.levels, price = r.decision.unit_price;
    const under = price * margin, over = price * (1 - margin) * overage, cr = under / (under + over);
    const qs = { baseline: r.baseline.quantiles, agent: r.final_quantiles };
    const cost = (o, d) => over * Math.max(o - d, 0) + under * Math.max(d - o, 0);
    const orders = {}, exp = {};
    for (const k in qs) orders[k] = Math.round(quantileAt(qs[k], cr, lv));
    const draws = Array.from({ length: 199 }, (_, i) => quantileAt(qs.agent, (i + 0.5) / 199, lv));
    for (const k in orders) exp[k] = r2(draws.reduce((a, d) => a + cost(orders[k], d), 0) / draws.length);
    const d = { unit_price: price, critical_ratio: Math.round(cr * 1e4) / 1e4, underage_per_unit: r3(under),
                overage_per_unit: r3(over), orders, expected_cost_under_agent: exp };
    if (r.decision.actual !== undefined) {
      const y = r.decision.actual;
      d.actual = y;
      d.realized_cost = { baseline: r2(cost(orders.baseline, y)), agent: r2(cost(orders.agent, y)) };
      d.pinball = { baseline: r3(pinball(y, qs.baseline, lv)), agent: r3(pinball(y, qs.agent, lv)) };
    }
    return { ...r, decision: d };
  }
  window.fetch = async (url, opts) => {
    const u = String(url);
    if (!u.startsWith("/api/")) return realFetch(url, opts);
    if (u !== "/api/forecast") return realFetch("api/" + u.slice(5) + ".json");
    const b = JSON.parse(opts.body);
    const note = (b.notes || "").trim();
    let suffix = "";
    if (note) {
      const i = NOTES.indexOf(note);
      if (i < 0) return fail("this static demo has the example notes pre-run on the GPU; free-text notes need the live server (see the README)");
      suffix = "_n" + i;
    }
    let res = await realFetch(`api/forecast/${b.sku_id}/${b.target_index}${suffix}.json`);
    if (!res.ok && suffix) return fail("the example notes are pre-run for upcoming weeks only; pick a week after today");
    if (!res.ok) return fail("week not exported");
    return ok(decide(await res.json(), b.margin_pct, b.overage_pct));
  };
})();
</script>
"""


def example_notes() -> list[str]:
    html = (WEB_DIR / "index.html").read_text()
    block = re.search(r"const EXAMPLES = \[(.*?)\];", html, re.S).group(1)
    return [json.loads(s) for s in re.findall(r'"(?:[^"\\]|\\.)*"', block)]


async def export(app, out: Path, notes: list[str], concurrency: int) -> None:
    api = out / "api"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://static") as c:
        for name in ("info", "skus", "backtest", "bench"):
            r = await c.get(f"/api/{name}")
            r.raise_for_status()
            body = r.json()
            if name == "info":
                body |= {"mode": "replay", "endpoint_ok": None}
            (api / f"{name}.json").write_text(json.dumps(body))
        skus = (await c.get("/api/skus")).json()

        jobs = []
        for s in skus:
            for w in s["weeks"]:
                jobs.append((s["sku_id"], w["index"], None, ""))
                if w["index"] >= s["default_index"]:
                    jobs += [(s["sku_id"], w["index"], n, f"_n{i}") for i, n in enumerate(notes)]
        sem = asyncio.Semaphore(concurrency)
        done = 0

        async def one(sku: str, t: int, note: str | None, suffix: str) -> None:
            nonlocal done
            async with sem:
                r = await c.post("/api/forecast", json={"sku_id": sku, "target_index": t, "notes": note}, timeout=600)
            r.raise_for_status()
            d = api / "forecast" / sku
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{t}{suffix}.json").write_text(json.dumps(r.json()))
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)} forecasts exported", flush=True)

        await asyncio.gather(*(one(*j) for j in jobs))
        print(f"exported {len(jobs)} forecasts")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="data/synthetic-store.json")
    ap.add_argument("--results", default="results")
    ap.add_argument("--cache", default="results/llm_cache.sqlite")
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--out", default="site")
    ap.add_argument("--live", action="store_true", help="compute cache misses on the model endpoint")
    ap.add_argument("--concurrency", type=int, default=64)
    args = ap.parse_args()

    ns = argparse.Namespace(base_url=None, model=None, cache=args.cache)
    ds = _dataset(args.dataset)
    agent = ForecastAgent(_llm(ns, offline=not args.live), n_samples=args.samples)
    app = create_app(ds, agent, results_dir=args.results, mode="live" if args.live else "replay")

    out = Path(args.out)
    shutil.rmtree(out, ignore_errors=True)
    (out / "api").mkdir(parents=True)
    notes = example_notes()
    asyncio.run(export(app, out, notes, args.concurrency))
    html = (WEB_DIR / "index.html").read_text()
    shim = SHIM.replace("__NOTES__", json.dumps(notes))
    (out / "index.html").write_text(html.replace("<script", shim + "<script", 1))
    (out / ".nojekyll").write_text("")
    print(f"wrote {out}/index.html")


if __name__ == "__main__":
    main()
