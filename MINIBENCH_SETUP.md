# MiniBench operation

The bot account is **SoundlyLunarBot (309116)**. Startup rejects another account's
Metaculus token. Keep the token in the existing GitHub Actions repository secret
`METACULUS_TOKEN`; never commit it or paste it into chat.

## Model access

The failed October 2 run selected `metaculus/gpt-4o-search-preview` implicitly.
The proxy rejected it because that model had no allowance. A Metaculus token
alone is not a model-provider subscription or model allowance.

Set GitHub Actions repository **variables** (not secrets):

- `FORECAST_MODEL`: the exact provider/model enabled on your account.
- `RESEARCH_MODEL`: a web-search-capable model, `asknews/news-summaries`, or
  `smart-searcher/<provider/model>` with an Exa key.
- `PARSER_MODEL`: optional; otherwise the forecast model is reused.

Put matching provider keys in Actions **secrets**. The runner retains support
for OpenRouter, OpenAI, Anthropic, Perplexity, AskNews, Exa, and explicitly selected
Metaculus proxy models. Do not choose a model until its access is confirmed.
The official template links the current participation/credits form:
https://github.com/Metaculus/metac-bot-template#readme

### Free Gemini tier (current default)

Metaculus declined this season's credit grant, so the workflows use free Gemini
models through the `GEMINI_API_KEY` secret: `gemini/gemini-3.6-flash` to research and
forecast, `gemini/gemini-3.5-flash-lite` to parse. When a model's daily quota is spent,
calls step down to `GEMINI_FALLBACK_MODEL`. Repository variables `FORECAST_MODEL`,
`RESEARCH_MODEL` (each may be a comma-separated list) and `PARSER_MODEL` override this.

`gemini_llm.py` calls the Gemini REST API directly, with the key in a header
(LiteLLM puts it in failed-request URLs). All Gemini calls in a run share one
pacer: at most one request every 4.6 s (`GEMINI_MIN_INTERVAL_SECONDS`) and at
most `GEMINI_MAX_REQUESTS_PER_RUN` (200) per run. A daily-quota 429 stops the batch.

Google Search grounding has no free allowance on this account (every model
returns 429), so research uses Google News RSS headlines plus Gemini's
`url_context` tool on pages named in the question. It refuses to forecast when
neither yields a source. Each question costs about 2 research requests plus
3 per prediction (forecast + 2 parser checks): 17 at the default 5 predictions.
Set the variable `PREDICTIONS_PER_QUESTION` lower to stretch the daily quota.

### Two runners, one forecast per question

The rules ask for one forecast per question, and only the last forecast before close is
scored, so the two runners split the window and never want the same question:

- **Local runner (first choice).** `scripts/run_local.sh`, started every five minutes by the
  launchd agent `scripts/com.hudson.futureeval-bot.plist`. It takes questions with more than
  110 minutes left, which leaves a pass half an hour before the backup's window opens. Research: Claude and Codex web search side by side, a follow-up search on
  gaps and conflicts, and a keyless Polymarket and Manifold lookup. Five forecasts (three
  gpt-6.1-sol, one Claude Opus, one Claude Sonnet); the median is posted. The bot token is read from the macOS keychain item
  `metaculus-bot-token` (account `SoundlyLunarBot`) and is never written to a file.
- **Hosted backup.** The GitHub workflow, on free Gemini models. Set the repository variable
  `ONLY_CLOSING_WITHIN_MINUTES=75` once the local runner is on, then restart the workflow;
  with no value it takes every open question at once.

To install the local runner, keep the repository in `~/futureeval-bot` (macOS does not let launchd
jobs read `~/Documents`; the job exits with code 127 there):

```sh
security add-generic-password -U -s metaculus-bot-token -a SoundlyLunarBot -w
cp scripts/com.hudson.futureeval-bot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hudson.futureeval-bot.plist
```

`scripts/replay.py` and `scripts/dry_run.py` test changes on closed questions and post nothing.
Do not test on open tournament questions: that counts as a human in the loop under the rules.

### Existing local model service

For local execution, `.env` can select the existing authenticated Responses
service without copying provider credentials:

```dotenv
LOCAL_MODEL_BASE_URL=http://127.0.0.1:10100/v1
FORECAST_MODEL=gpt-6.1-sol
RESEARCH_MODEL=gpt-6.1-sol
PARSER_MODEL=gpt-6.1-sol
```

The local adapter requires a loopback address, forces an actual web search for
research, preserves source URLs, and rejects incomplete or empty responses.
It bypasses the locked LiteLLM transport's missing optional FastAPI dependency.
Token usage is saved separately; dollar cost is unknown rather than reported as
zero. The local route still requires the bot's Metaculus token. GitHub-hosted
Actions cannot use this loopback URL; cloud execution requires its own approved
provider credentials. Keep the local gateway private.

## Inspect and preview

`Diagnose and Preview Bot` defaults to an inventory-only run: it reads current
open MiniBench questions and saves `inventory.json`, with no model calls and no
forecast submission. Choose `test_questions` to forecast on the bot-testing-area tournament.
Set `inventory_only=false` and `limit=1` for a one-question forecast preview after
configuring model access. Inspect the resulting artifact before a full run.

```sh
poetry install --only main --no-interaction --no-root
poetry run python main.py --mode minibench --inventory-only
poetry run python main.py --mode minibench --limit 1
poetry run python main.py --mode minibench
```

The runner uses one event loop, processes the earliest closing questions first,
skips saved forecasts, checks model access before forecasting, and saves every
successful forecast immediately. Authentication/quota failures stop the batch.
Research is mandatory; failed research is not silently replaced by an uninformed
forecast. Independent forecast samples per question default to five.

## Publish

Add `--publish` only when ready to submit forecasts and private explanations.
`Forecast on FutureEval and MiniBench` still targets both tournaments, with
MiniBench first. Workflow enablement is separate from code deployment. The
repair does not enable the previously disabled publishing workflow.

Reports and question inventories are stored in Actions artifacts (14 days), not
committed to the public repository. Model metadata records model names only;
SDK dictionaries containing authentication headers are excluded.
