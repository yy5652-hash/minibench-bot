"""Run the whole pipeline on closed questions from saved reports. Nothing is posted.

These questions are past their forecast window, so searching now shows only a few extra
days of news. Used to check the pipeline end to end and to compare it with the old forecast.
  .venv/bin/python scripts/dry_run.py --posts 46277,46280 --predictions 4
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from forecasting_tools import ForecastBot  # noqa: E402
from forecasting_tools.data_models.data_organizer import DataOrganizer  # noqa: E402

import main as bot_main  # noqa: E402
from bot_runtime import model_config  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / ".data"


def bot_class() -> type:
    return next(v for v in vars(bot_main).values()
                if isinstance(v, type) and issubclass(v, ForecastBot) and v is not ForecastBot)


def saved_question(post: int):
    for path in glob.glob(str(DATA / "art/*/*/forecast-*.json")):
        raw = json.load(open(path, encoding="utf-8"))
        if raw and raw[0]["question"]["id_of_post"] == post:
            question = DataOrganizer.load_reports_from_file_path(path)[0].question
            question.already_forecasted = False
            return question
    raise KeyError(post)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts", required=True)
    parser.add_argument("--predictions", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    out = DATA / "dry_run.json"
    results = json.loads(out.read_text()) if out.exists() else {}
    bot = bot_class()(
        research_reports_per_question=1, predictions_per_research_report=args.predictions,
        use_research_summary_to_forecast=False, enable_summarize_research=False,
        publish_reports_to_metaculus=False, folder_to_save_reports_to=None,
        skip_previously_forecasted_questions=False, extra_metadata_in_explanation=False,
        llms=model_config())
    slots = asyncio.Semaphore(args.concurrency)

    async def one(post: int) -> None:
        if str(post) in results:
            return
        question = saved_question(post)
        started = time.time()
        async with slots:
            report = await bot.forecast_question(question, return_exceptions=True)
        if isinstance(report, BaseException):
            print(f"{post} FAILED {type(report).__name__}: {str(report)[:300]}", flush=True)
            return
        results[str(post)] = {"type": question.question_type if hasattr(question, "question_type") else "",
                              "prediction": json.loads(report.model_dump_json())["prediction"],
                              "minutes": round((time.time() - started) / 60, 1),
                              "errors": [str(e)[:200] for e in report.errors],
                              "explanation": report.explanation}
        out.write_text(json.dumps(results, indent=1))
        print(f"{post} done in {results[str(post)]['minutes']} min, errors={len(report.errors)}", flush=True)

    await asyncio.gather(*(one(int(p)) for p in args.posts.split(",")))


if __name__ == "__main__":
    asyncio.run(main())
