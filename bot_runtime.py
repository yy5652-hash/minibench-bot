"""Explicit model configuration and a resumable, deadline-ordered runner."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from forecasting_tools import ApiFilter, ForecastReport, GeneralLlm, MetaculusClient

from bot_helpers import _is_real_env, print_run_summary_banner


def model_config() -> dict:
    """Never silently select a proxy model with an unassigned allowance."""
    forecast = os.getenv("FORECAST_MODEL", "").strip()
    researcher = os.getenv("RESEARCH_MODEL", "").strip()
    if not forecast or not researcher:
        raise ValueError(
            "Set FORECAST_MODEL and RESEARCH_MODEL to models your provider has enabled. "
            "A METACULUS_TOKEN alone does not grant model credits. "
            "Use the participant/credits form linked from the official template README."
        )
    if researcher.lower() in {"none", "no_research"}:
        raise ValueError("A current-evidence research provider is required.")
    parser = os.getenv("PARSER_MODEL", "").strip() or forecast

    def llm(name: str) -> GeneralLlm:
        # Do not send temperature to reasoning/search models that reject it.
        return GeneralLlm(model=name, timeout=180, allowed_tries=2)

    research = researcher if researcher.startswith(("asknews/", "smart-searcher/")) else llm(researcher)
    if researcher.startswith("asknews/") and not (
        _is_real_env("ASKNEWS_API_KEY")
        or (_is_real_env("ASKNEWS_CLIENT_ID") and _is_real_env("ASKNEWS_SECRET"))
    ):
        raise ValueError("The selected AskNews researcher has no configured credentials.")
    if researcher.startswith("smart-searcher/") and not _is_real_env("EXA_API_KEY"):
        raise ValueError("The selected SmartSearcher needs EXA_API_KEY.")
    return {"default": llm(forecast), "researcher": research,
            "parser": llm(parser), "summarizer": llm(parser)}


def safe_model_names(bot) -> dict[str, str]:
    # GeneralLlm.to_dict() includes authentication headers in this SDK version.
    # Never put those dictionaries in reports, logs, or forecast comments.
    return {role: value.model if isinstance(value, GeneralLlm) else str(value)
            for role, value in bot._llms.items()}


async def preflight(bot) -> None:
    """Fail before a whole batch if a forecast/parser model is inaccessible."""
    checked = set()
    for role in ("default", "parser"):
        model = bot.get_llm(role, "llm")
        if model.model not in checked:
            print(f"Checking model access: {role}={model.model}")
            reply = await model.invoke("Reply with only the word READY.")
            if not reply.strip():
                raise RuntimeError(f"Empty model response for {role}")
            checked.add(model.model)


async def run(bot_class, args) -> int:
    client = MetaculusClient()
    bot_id = client.get_current_user_id()
    if bot_id != 309116:
        raise RuntimeError("METACULUS_TOKEN does not belong to SoundlyLunarBot (309116).")
    print(f"Authenticated bot ID: {bot_id}")
    provider_names = ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
                      "PERPLEXITY_API_KEY", "ASKNEWS_API_KEY", "ASKNEWS_CLIENT_ID",
                      "ASKNEWS_SECRET", "EXA_API_KEY")
    print("Configured provider credentials (names only):", [n for n in provider_names if _is_real_env(n)])
    tournaments = {
        "minibench": ["minibench"],
        "tournament": ["minibench", "fall-futureeval-2026"],
        "test_questions": ["bot-testing-area"],
        "metaculus_cup": [client.CURRENT_METACULUS_CUP_ID],
    }[args.mode]
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    questions = []
    seen = set()
    for tournament in tournaments:
        found = await client.get_questions_matching_filter(ApiFilter(
            allowed_tournaments=[tournament], allowed_statuses=["open"],
            group_question_mode="unpack_subquestions"))
        for question in found:
            if question.id_of_question not in seen:
                questions.append(question)
                seen.add(question.id_of_question)
    questions.sort(key=lambda q: q.close_time or datetime.max.replace(tzinfo=timezone.utc))
    pending = [q for q in questions if not q.already_forecasted or args.mode == "test_questions"]
    manifest = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "open": len(questions), "unpredicted": len(pending),
        "questions": [{"id": q.id_of_question, "url": q.page_url,
                       "title": q.question_text, "close_time": str(q.close_time),
                       "resolution_criteria": q.resolution_criteria,
                       "fine_print": q.fine_print, "background_info": q.background_info,
                       "already_forecasted": q.already_forecasted} for q in questions],
    }
    (output / "inventory.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Open questions: {len(questions)}; unpredicted: {len(pending)}")
    for q in pending:
        print(f"  {q.close_time} | {q.page_url} | {q.question_text}")
    if args.inventory_only or not pending:
        return 0
    if args.limit:
        pending = pending[:args.limit]
    bot = bot_class(
        research_reports_per_question=1, predictions_per_research_report=args.predictions,
        use_research_summary_to_forecast=False, enable_summarize_research=False,
        publish_reports_to_metaculus=args.publish, folder_to_save_reports_to=None,
        skip_previously_forecasted_questions=args.mode != "test_questions",
        extra_metadata_in_explanation=False, llms=model_config(),
        metaculus_client=client,
    )
    print("Models:", json.dumps(safe_model_names(bot)))
    await preflight(bot)
    reports = []
    for question in pending:
        if question.close_time and question.close_time <= datetime.now(timezone.utc):
            print(f"Skipped now-closed question: {question.page_url}")
            continue
        report = await bot.forecast_question(question, return_exceptions=True)
        reports.append(report)
        if isinstance(report, ForecastReport):
            ForecastReport.save_object_list_to_file_path(
                [report], str(output / f"forecast-{question.id_of_question}.json"))
        else:
            print(f"Failed {question.page_url}: {type(report).__name__}")
            # A batch-wide configuration error must not be retried on 60 questions.
            message = str(report).lower()
            if any(s in message for s in ("allowance", "api key", "api_key", "quota", "authentication")):
                print("Provider access/credit failure: stopping this batch.")
                break
    print_run_summary_banner(reports, args.publish)
    return 1 if any(isinstance(r, BaseException) for r in reports) else 0
