"""Inference benchmark against the live vLLM endpoint.

Sends real forecasting requests (distinct prompts, ``n`` samples each) at
several concurrency levels and reports throughput, latency and the GPU cost
per 1,000 forecasts. Run it on the GPU host so the GPU description can be
captured from ``rocm-smi`` / ``amd-smi``.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
from datetime import datetime, timezone

import numpy as np

from .agent import OUTPUT_SCHEMA, ForecastAgent, parse_adjustment
from .data import Dataset
from .llm import OpenAICompatibleLLM


def gpu_info() -> str | None:
    """Text from the AMD GPU tools on this host, or None if they are absent."""
    cmds = [
        ["amd-smi", "static", "--asic", "--vram"],
        ["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--showdriverversion"],
    ]
    for cmd in cmds:
        if shutil.which(cmd[0]):
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if out.returncode == 0 and out.stdout.strip():
                return f"$ {' '.join(cmd)}\n{out.stdout.strip()}"
    return None


async def run_bench(
    llm: OpenAICompatibleLLM,
    dataset: Dataset,
    concurrencies: tuple[int, ...] = (1, 8, 32, 64, 128),
    n_samples: int = 5,
    price_per_hour: float = 1.99,
    max_requests_per_level: int = 256,
    progress=print,
) -> dict:
    if llm.cache is not None:
        raise ValueError("benchmark must run without a response cache")
    agent = ForecastAgent(llm=None, n_samples=n_samples)

    # A pool of distinct prompts, walking back through history so no two requests repeat.
    pool: list[list[dict]] = []
    for back in range(0, 60):
        for s in dataset.series:
            t = s.last_known_index() - back
            if t > 30:
                pool.append(agent.build(s, t)[1])
    cursor = 0

    levels = []
    for c in concurrencies:
        n_req = min(max(2 * c, 16), max_requests_per_level)
        batch = pool[cursor:cursor + n_req]
        cursor += n_req
        if len(batch) < n_req:
            raise ValueError("not enough distinct prompts for the benchmark; use a larger dataset")
        sem = asyncio.Semaphore(c)
        lat: list[float] = []
        out_tok = in_tok = parsed = total = 0

        async def one(msgs):
            nonlocal out_tok, in_tok, parsed, total
            async with sem:
                t0 = time.perf_counter()
                comp = await llm.complete(msgs, n=n_samples, schema=OUTPUT_SCHEMA)
                lat.append(time.perf_counter() - t0)
            out_tok += comp.completion_tokens
            in_tok += comp.prompt_tokens
            total += len(comp.texts)
            parsed += sum(parse_adjustment(t) is not None for t in comp.texts)

        t0 = time.perf_counter()
        await asyncio.gather(*(one(m) for m in batch))
        wall = time.perf_counter() - t0
        per_hour = 3600.0 * n_req / wall
        row = {
            "concurrency": c,
            "requests": n_req,
            "wall_s": round(wall, 2),
            "forecasts_per_min": round(60.0 * n_req / wall, 1),
            "output_tok_per_s": round(out_tok / wall, 1),
            "total_tok_per_s": round((out_tok + in_tok) / wall, 1),
            "mean_prompt_tokens": round(in_tok / n_req, 1),
            "mean_completion_tokens_per_sample": round(out_tok / max(total, 1), 1),
            "p50_latency_s": round(float(np.percentile(lat, 50)), 3),
            "p95_latency_s": round(float(np.percentile(lat, 95)), 3),
            "usd_per_1k_forecasts": round(1000.0 * price_per_hour / per_hour, 4),
            "parse_rate": round(parsed / max(total, 1), 4),
        }
        levels.append(row)
        if progress:
            progress(f"concurrency {c:>4}: {row['forecasts_per_min']:>8.1f} forecasts/min, "
                     f"{row['output_tok_per_s']:>8.1f} out tok/s, p95 {row['p95_latency_s']:.2f}s")

    return {
        "model": llm.model,
        "endpoint": llm.config.base_url,
        "n_samples": n_samples,
        "price_per_hour": price_per_hour,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gpu_info": gpu_info(),
        "levels": levels,
    }
