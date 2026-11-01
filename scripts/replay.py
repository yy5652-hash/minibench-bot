"""Replay closed binary questions from saved reports with the research the bot had at the time.

Nothing is posted. The research text and the stated date are those of the original forecast,
and the models cannot search, so the outcome cannot leak in. Usage:
  .venv/bin/python scripts/replay.py --models claude-cli/claude-opus-5-5,codex/gpt-6.1-sol --samples 1
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import math
import re
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli_llm import CliLlm  # noqa: E402
from local_responses import LocalResponsesLlm  # noqa: E402
from prompts import binary_prompt  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / ".data"
GATEWAY = "http://127.0.0.1:10100/v1"


def load_cases() -> list[dict]:
    reports = {}
    for path in glob.glob(str(DATA / "art/*/*/forecast-*.json")):
        for report in json.load(open(path, encoding="utf-8")):
            reports[report["question"]["id_of_post"]] = report
    cases = []
    for token in (DATA / "outcomes_binary.txt").read_text().split():
        short, outcome, community, _ = token.split(":")
        post = 46000 + int(short)
        report = reports[post]
        question = report["question"]
        match = re.search(r"# RESEARCH\n(.*?)\n# FORECASTS", report["explanation"], re.S)
        cases.append({"post": post, "outcome": outcome, "community": float(community),
                      "old": report["prediction"], "research": match.group(1) if match else "",
                      "today": question["open_time"][:10],
                      "question": SimpleNamespace(
                          question_text=question["question_text"], background_info=question["background_info"],
                          resolution_criteria=question["resolution_criteria"], fine_print=question["fine_print"],
                          close_time=question["close_time"],
                          scheduled_resolution_time=question["scheduled_resolution_time"])})
    return cases


def make_llm(name: str):
    if name.startswith(("codex/", "claude/")):
        return CliLlm(name)
    return LocalResponsesLlm(name, GATEWAY)


def parse_probability(text: str) -> float | None:
    found = re.findall(r"Probability:\s*\**\s*([0-9]+(?:\.[0-9]+)?)\s*%", text)
    return min(0.98, max(0.02, float(found[-1]) / 100)) if found else None


async def forecast(llm, case: dict, slots: asyncio.Semaphore) -> float | None:
    prompt = binary_prompt(case["question"], case["research"], case["today"])
    async with slots:
        for _ in range(2):
            try:
                value = parse_probability(await llm.invoke(prompt))
                if value is not None:
                    return value
            except Exception as error:
                print(f"{llm.model} on {case['post']}: {type(error).__name__}: {str(error)[:120]}", flush=True)
    return None


def peer(p: float, case: dict) -> float:
    """Log score against the community forecast, the usual stand-in for the peer score."""
    yes = case["outcome"] == "y"
    return 100 * (math.log(p if yes else 1 - p) - math.log(case["community"] if yes else 1 - case["community"]))


def summary(name: str, values: dict, cases: list[dict]) -> None:
    resolved = [c for c in cases if c["outcome"] in ("y", "n") and values.get(c["post"]) is not None]
    closed = [c for c in cases if values.get(c["post"]) is not None]
    scores = [peer(values[c["post"]], c) for c in resolved]
    brier = statistics.mean((values[c["post"]] - (c["outcome"] == "y")) ** 2 for c in resolved) if resolved else 0
    spread = statistics.mean(abs(values[c["post"]] - c["community"]) for c in closed) if closed else 0
    print(f"{name:42s} n={len(resolved):2d} peer {statistics.mean(scores) if scores else 0:+6.1f} "
          f"brier {brier:.3f} | all n={len(closed):2d} gap to community {spread:.3f}", flush=True)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--resolved-only", action="store_true")
    args = parser.parse_args()
    cases = load_cases()
    if args.resolved_only:
        cases = [c for c in cases if c["outcome"] in ("y", "n")]
    out = DATA / "replay.json"
    results = json.loads(out.read_text()) if out.exists() else {}
    slots = asyncio.Semaphore(args.concurrency)
    for name in args.models.split(","):
        llm = make_llm(name)
        known = results.setdefault(name, {})
        todo = [(c, i) for c in cases for i in range(args.samples) if len(known.get(str(c["post"]), [])) <= i]
        replies = await asyncio.gather(*(forecast(llm, c, slots) for c, _ in todo))
        for (case, _), value in zip(todo, replies):
            if value is not None:
                known.setdefault(str(case["post"]), []).append(value)
        out.write_text(json.dumps(results, indent=1))
    print(f"questions: {len(cases)}")
    summary("old bot (flash-lite)", {c["post"]: min(.98, max(.02, c["old"])) for c in cases}, cases)
    medians = {name: {int(k): statistics.median(v) for k, v in by.items() if v} for name, by in results.items()}
    for name, values in medians.items():
        summary(name, values, cases)
    if len(medians) > 1:
        team = {c["post"]: statistics.median(v[c["post"]] for v in medians.values() if c["post"] in v)
                for c in cases if any(c["post"] in v for v in medians.values())}
        summary("median of all models above", team, cases)


if __name__ == "__main__":
    asyncio.run(main())
