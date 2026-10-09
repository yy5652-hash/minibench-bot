"""Markdown reports for backtest and benchmark results."""

from __future__ import annotations

NAMES = {
    "snaive": "Seasonal naive (same week last year)",
    "baseline": "Statistical baseline (exp. smoothing)",
    "baseline_cal": "Baseline + calibration",
    "rule": "Classical uplift rule (no LLM, ablation)",
    "rule_cal": "Uplift rule + calibration",
    "agent": "ShelfCast agent (raw)",
    "agent_cal": "ShelfCast agent + calibration",
}


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _table(block: dict) -> list[str]:
    rows = [
        "| Method | Scaled pinball ↓ | WAPE ↓ | Bias | 80% cov. | 90% cov. | Inventory cost ↓ | Fill rate | Stockout weeks |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m, name in NAMES.items():
        s = block.get(m)
        if not s or "scaled_pinball" not in s:
            continue
        rows.append(
            f"| {name} | {s['scaled_pinball']:.4f} | {_pct(s['wape_median'])} | {s['bias_median_pct']:+.1f}% | "
            f"{_pct(s['coverage_80'])} | {_pct(s['coverage_90'])} | ${s['total_cost']:,.0f} | "
            f"{_pct(s['fill_rate'])} | {_pct(s['stockout_rate'])} |"
        )
    return rows


def _headline(block: dict) -> str:
    parts = []
    if "fva_pinball_pct" in block:
        parts.append(f"forecast value add **{block['fva_pinball_pct']:+.1f}%** (scaled pinball, calibrated agent vs calibrated baseline; raw vs raw {block.get('fva_pinball_raw_pct', 0):+.1f}%)")
    if "fva_vs_rule_pct" in block:
        parts.append(f"vs classical uplift rule **{block['fva_vs_rule_pct']:+.1f}%**")
    if "cost_saving_pct" in block:
        parts.append(f"inventory cost **{-block['cost_saving_pct']:+.1f}%** vs calibrated baseline")
    return "; ".join(parts)


def backtest_markdown(res: dict) -> str:
    m, s, llm = res["meta"], res["summary"], res["llm"]
    cfg = m["config"]
    lines = [
        f"# ShelfCast backtest: {m['dataset']}",
        "",
        f"{m['description']}",
        "",
        f"- Forecasts: **{m['n_forecasts']}** ({m['n_series']} series × last {cfg['n_origins']} weeks, "
        f"{m['weeks'][0]} to {m['weeks'][-1]}), one week ahead",
        f"- Model: `{llm['model']}`, {llm['samples_per_forecast']} samples per forecast; "
        f"LLM answered {llm['llm_ok']}/{llm['forecasts']}",
        f"- Economics: margin {cfg['margin_pct']:.0%} of price, leftover cost {cfg['overage_pct']:.0%} of unit cost "
        "(newsvendor order at the critical ratio)",
        f"- Generated {m['created_at']}",
        "",
        "## All weeks",
        "",
        _headline(s),
        "",
        *_table(s),
        "",
        "## Event weeks (holidays, promotions, other calendar events)",
        "",
        _headline(res["segments"]["event_weeks"]),
        "",
        *_table(res["segments"]["event_weeks"]),
        "",
        "## Ordinary weeks",
        "",
        _headline(res["segments"]["ordinary_weeks"]),
        "",
        *_table(res["segments"]["ordinary_weeks"]),
        "",
        "## By category",
        "",
        "| Category | Forecasts | FVA (pinball) | Inventory cost change |",
        "|---|---:|---:|---:|",
    ]
    for c, b in res["by_category"].items():
        lines.append(f"| {c} | {b['agent_cal']['n']} | {b.get('fva_pinball_pct', 0):+.1f}% | "
                     f"{-b.get('cost_saving_pct', 0):+.1f}% |")
    lines += [
        "",
        "## Inference",
        "",
        f"- Prompt tokens {llm['prompt_tokens']:,}, completion tokens {llm['completion_tokens']:,}",
        f"- Wall time {llm['wall_time_s']:.1f}s, mean request latency "
        f"{'n/a' if llm['mean_latency_s'] is None else str(llm['mean_latency_s']) + 's'}, "
        f"{llm['cached']} responses served from cache",
    ]
    if llm["errors"]:
        lines.append(f"- Errors seen: {'; '.join(llm['errors'])}")
    lines += [
        "",
        "Scaled pinball is the mean quantile loss over 11 levels divided by the SKU's mean weekly demand "
        "(lower is better). FVA is the relative improvement of the calibrated agent over the calibrated "
        "statistical baseline, so calibration is never credited to the model. Calibrated variants are fit "
        "only on earlier weeks.",
    ]
    return "\n".join(lines) + "\n"


def bench_markdown(res: dict) -> str:
    lines = [
        "# ShelfCast inference benchmark",
        "",
        f"- Endpoint model: `{res['model']}`",
        f"- Samples per forecast: {res['n_samples']}; GPU price used for cost: ${res['price_per_hour']:.2f}/hour",
        f"- Generated {res['created_at']}",
        "",
        "| Concurrent forecasts | Forecasts/min | Output tok/s | p50 latency | p95 latency | $ per 1,000 forecasts | Parsed |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in res["levels"]:
        lines.append(
            f"| {r['concurrency']} | {r['forecasts_per_min']:,.0f} | {r['output_tok_per_s']:,.0f} | "
            f"{r['p50_latency_s']:.2f}s | {r['p95_latency_s']:.2f}s | ${r['usd_per_1k_forecasts']:.3f} | "
            f"{_pct(r['parse_rate'])} |"
        )
    if res.get("gpu_info"):
        lines += ["", "## GPU", "", "```", res["gpu_info"].strip(), "```"]
    return "\n".join(lines) + "\n"


README_START = "<!-- RESULTS:START -->"
README_END = "<!-- RESULTS:END -->"


def _signed(x: float | None) -> str:
    return "n/a" if x is None else f"{x:+.1f}%"


def headline_markdown(backtests: list[dict], bench: dict | None) -> str:
    """Headline numbers for the README, taken verbatim from the result files."""
    lines: list[str] = []
    for bt in backtests:
        m, s, llm = bt["meta"], bt["summary"], bt["llm"]
        ev, od = bt["segments"]["event_weeks"], bt["segments"]["ordinary_weeks"]
        label = "Synthetic store" if m["source"] == "synthetic" else "Real Walmart sales (M5)"
        lines += [
            f"**{label}**: {m['n_forecasts']:,} one-week-ahead forecasts, {m['n_series']} SKUs, "
            f"{m['weeks'][0]} to {m['weeks'][-1]}; model `{llm['model']}`, {llm['samples_per_forecast']} samples "
            f"each, answered {llm['llm_ok']}/{llm['forecasts']}.",
            "",
            "| (all three calibrated on earlier weeks) | Statistical baseline | Uplift rule, no LLM | ShelfCast |",
            "|---|---:|---:|---:|",
        ]

        def row(name: str, block: dict, key: str, fmt) -> str:
            vals = [block.get(k, {}).get(key) for k in ("baseline_cal", "rule_cal", "agent_cal")]
            return f"| {name} | " + " | ".join("n/a" if v is None else fmt(v) for v in vals) + " |"

        lines += [
            row("Scaled pinball loss ↓, all weeks", s, "scaled_pinball", lambda v: f"{v:.4f}"),
            row("Scaled pinball loss ↓, event weeks", ev, "scaled_pinball", lambda v: f"{v:.4f}"),
            row("Scaled pinball loss ↓, ordinary weeks", od, "scaled_pinball", lambda v: f"{v:.4f}"),
            row("90% interval coverage (target 90%)", s, "coverage_90", _pct),
            row("Inventory cost ↓ (leftovers + lost margin)", s, "total_cost", lambda v: f"${v:,.0f}"),
            row("Fill rate", s, "fill_rate", _pct),
            "",
            f"Forecast value add vs the calibrated baseline: **{_signed(s.get('fva_pinball_pct'))}** "
            f"(event weeks {_signed(ev.get('fva_pinball_pct'))}, ordinary weeks {_signed(od.get('fva_pinball_pct'))}); "
            f"vs the uplift rule: **{_signed(s.get('fva_vs_rule_pct'))}**; "
            f"inventory cost **{_signed(None if s.get('cost_saving_pct') is None else -s['cost_saving_pct'])}**.",
            "",
        ]
    if bench and bench.get("levels"):
        best = max(bench["levels"], key=lambda r: r["forecasts_per_min"])
        gpu = "the serving GPU"
        info = bench.get("gpu_info") or ""
        for tag in ("MI355X", "MI325X", "MI300X", "MI300A", "MI250X"):
            if tag in info:
                gpu = f"one AMD Instinct {tag}"
                break
        lines += [
            f"**Inference on {gpu}** (`{bench['model']}`, vLLM, {bench['n_samples']} samples per forecast): "
            f"{best['forecasts_per_min']:,.0f} forecasts/min at {best['concurrency']} concurrent requests, "
            f"{best['output_tok_per_s']:,.0f} output tokens/s, p95 latency {best['p95_latency_s']:.1f}s, "
            f"${best['usd_per_1k_forecasts']:.3f} per 1,000 forecasts at ${bench['price_per_hour']:.2f}/GPU-hour; "
            f"{_pct(best['parse_rate'])} of samples parsed as valid JSON.",
            "",
        ]
    if not lines:
        return "No results yet: run `deploy/run_all.sh` on the GPU host.\n"
    return "\n".join(lines)


def write_readme_results(readme: str, block: str) -> str:
    """Replace the text between the RESULTS markers."""
    if README_START not in readme or README_END not in readme:
        raise ValueError("README has no RESULTS markers")
    head, rest = readme.split(README_START, 1)
    _, tail = rest.split(README_END, 1)
    return f"{head}{README_START}\n{block.rstrip()}\n{README_END}{tail}"
