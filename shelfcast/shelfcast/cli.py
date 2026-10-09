"""Command line: ``python -m shelfcast <command>``.

  data synthetic|m5   build a dataset file
  check               ping the model endpoint
  forecast            one forecast, printed
  backtest            rolling backtest -> results/backtest_<dataset>.json/.md
  bench               throughput benchmark -> results/bench.json/.md
  warm                pre-run forecasts for upcoming weeks so replay mode has them
  serve               demo web app
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .agent import ForecastAgent
from .data import Dataset, download_m5, generate_synthetic, load_m5
from .llm import LLMConfig, LLMUnavailable, OpenAICompatibleLLM, ResponseCache

DEFAULT_DATASET = "data/synthetic-store.json"
DEFAULT_CACHE = "results/llm_cache.sqlite"


def _llm(args, offline: bool = False, cache: bool = True) -> OpenAICompatibleLLM:
    cfg = LLMConfig.from_env()
    if getattr(args, "base_url", None):
        cfg.base_url = args.base_url
    if getattr(args, "model", None):
        cfg.model = args.model
    return OpenAICompatibleLLM(cfg, cache=ResponseCache(args.cache) if cache else None, offline=offline)


def _dataset(path: str) -> Dataset:
    p = Path(path)
    if not p.exists():
        if path == DEFAULT_DATASET:
            ds = generate_synthetic()
            ds.save(p)
            return ds
        sys.exit(f"dataset {path} not found; build it with `python -m shelfcast data ...`")
    return Dataset.load(p)


def _progress(every: int):
    def cb(done, total, fc):
        if done % every == 0 or done == total:
            flag = "" if fc.llm_ok else f"  [{fc.error}]"
            print(f"  {done}/{total} forecasts{flag}", flush=True)
    return cb


def cmd_data(args) -> None:
    if args.kind == "synthetic":
        ds = generate_synthetic(seed=args.seed)
    else:
        download_m5(args.m5_dir)
        ds = load_m5(args.m5_dir, n_series=args.n_series, seed=args.seed)
    out = args.out or f"data/{ds.name}.json"
    ds.save(out)
    print(f"wrote {out}: {len(ds.series)} series, {ds.series[0].n_weeks} weeks in the first one")


def cmd_check(args) -> None:
    llm = _llm(args, cache=False)
    try:
        models = asyncio.run(llm.list_models())
    except LLMUnavailable as e:
        sys.exit(f"endpoint not reachable: {e}")
    print(f"endpoint {llm.config.base_url} serves: {', '.join(models)}")
    if llm.model not in models:
        print(f"warning: configured model {llm.model} is not in that list (set SHELFCAST_LLM_MODEL)")


def cmd_forecast(args) -> None:
    ds = _dataset(args.dataset)
    s = ds.get(args.sku)
    t = args.week if args.week is not None else min(s.last_known_index() + 1, s.n_weeks - 1)
    agent = ForecastAgent(_llm(args, offline=args.offline), n_samples=args.samples)
    fc = asyncio.run(agent.forecast(s, t, notes=args.notes))
    print(json.dumps(fc.to_dict(include_context=args.brief), indent=2))


def cmd_backtest(args) -> None:
    from .backtest import BacktestConfig, run_backtest
    from .report import backtest_markdown

    ds = _dataset(args.dataset)
    agent = ForecastAgent(_llm(args, offline=args.offline), n_samples=args.samples)
    cfg = BacktestConfig(n_origins=args.origins, n_samples=args.samples, concurrency=args.concurrency)
    total = sum(1 for _ in ds.series) * args.origins
    print(f"backtest on {ds.name}: about {total} forecasts, {args.samples} samples each, model {agent.llm.model}")
    res = asyncio.run(run_backtest(ds, agent, cfg, progress=_progress(max(1, total // 20))))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"backtest_{ds.name}.json").write_text(json.dumps(res))
    md = backtest_markdown(res)
    (out / f"backtest_{ds.name}.md").write_text(md)
    print(md)


def cmd_bench(args) -> None:
    from .bench import run_bench
    from .report import bench_markdown

    ds = _dataset(args.dataset)
    llm = _llm(args, cache=False)
    levels = tuple(int(x) for x in args.concurrency.split(","))
    res = asyncio.run(run_bench(llm, ds, levels, n_samples=args.samples, price_per_hour=args.price_per_hour))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bench.json").write_text(json.dumps(res, indent=2))
    if res.get("gpu_info"):
        (out / "gpu_info.txt").write_text(res["gpu_info"])
    md = bench_markdown(res)
    (out / "bench.md").write_text(md)
    print(md)


def cmd_warm(args) -> None:
    ds = _dataset(args.dataset)
    agent = ForecastAgent(_llm(args), n_samples=args.samples)
    jobs = []
    for s in ds.series:
        last = s.last_known_index()
        jobs += [(s, t) for t in range(last + 1, min(s.n_weeks, last + 1 + args.weeks))]
    print(f"warming {len(jobs)} upcoming-week forecasts")
    res = asyncio.run(agent.forecast_many(jobs, concurrency=args.concurrency, progress=_progress(10)))
    print(f"{sum(r.llm_ok for r in res)}/{len(res)} answered by the model")


def cmd_serve(args) -> None:
    import uvicorn

    from .server import create_app

    ds = _dataset(args.dataset)
    offline = args.mode == "replay"
    agent = ForecastAgent(_llm(args, offline=offline), n_samples=args.samples)
    app = create_app(ds, agent, results_dir=args.out_dir, mode=args.mode)
    uvicorn.run(app, host=args.host, port=args.port)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="shelfcast", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, dataset=True):
        if dataset:
            sp.add_argument("--dataset", default=DEFAULT_DATASET)
        sp.add_argument("--base-url", help="OpenAI-compatible endpoint (default: $SHELFCAST_LLM_BASE_URL)")
        sp.add_argument("--model", help="model id (default: $SHELFCAST_LLM_MODEL)")
        sp.add_argument("--cache", default=DEFAULT_CACHE)
        sp.add_argument("--samples", type=int, default=5)
        sp.add_argument("--out-dir", default="results")

    sp = sub.add_parser("data")
    sp.add_argument("kind", choices=["synthetic", "m5"])
    sp.add_argument("--m5-dir", default="data/m5")
    sp.add_argument("--n-series", type=int, default=60)
    sp.add_argument("--seed", type=int, default=7)
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_data)

    sp = sub.add_parser("check")
    common(sp, dataset=False)
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("forecast")
    common(sp)
    sp.add_argument("--sku", required=True)
    sp.add_argument("--week", type=int, help="target week index (default: next week)")
    sp.add_argument("--notes")
    sp.add_argument("--brief", action="store_true", help="include the prompt brief")
    sp.add_argument("--offline", action="store_true")
    sp.set_defaults(func=cmd_forecast)

    sp = sub.add_parser("backtest")
    common(sp)
    sp.add_argument("--origins", type=int, default=26)
    sp.add_argument("--concurrency", type=int, default=64)
    sp.add_argument("--offline", action="store_true", help="re-score from the cache without calling the model")
    sp.set_defaults(func=cmd_backtest)

    sp = sub.add_parser("bench")
    common(sp)
    sp.add_argument("--concurrency", default="1,8,32,64,128")
    sp.add_argument("--price-per-hour", type=float, default=1.99)
    sp.set_defaults(func=cmd_bench)

    sp = sub.add_parser("warm")
    common(sp)
    sp.add_argument("--weeks", type=int, default=8)
    sp.add_argument("--concurrency", type=int, default=64)
    sp.set_defaults(func=cmd_warm)

    sp = sub.add_parser("serve")
    common(sp)
    sp.add_argument("--mode", choices=["live", "replay"], default="live")
    sp.add_argument("--host", default="0.0.0.0")
    sp.add_argument("--port", type=int, default=8080)
    sp.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
