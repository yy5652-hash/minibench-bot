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
forecast submission. The repair branch push also runs this same diagnostic.
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
