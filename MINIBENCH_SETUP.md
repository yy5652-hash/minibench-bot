# MiniBench setup

This fork forecasts on Fall FutureEval 2026 and MiniBench. All runs happen on
the owner's computer: `run_local.py` calls `main.py --mode tournament --publish`
every 20 minutes and skips questions the bot has already forecast. The GitHub
Actions workflows are manual-only fallbacks with no schedule. See
[LOCAL_RUN.md](LOCAL_RUN.md) for the full commands.

The Metaculus bot account is `SoundlyLunarBot`. Its API token must be handled
by the account owner; never commit it or paste it into an issue or chat. Keep
it in the local, git-ignored `.env`.

```sh
poetry install
cp .env.template .env                     # fill in METACULUS_TOKEN + a model key
poetry run python main.py --mode test_questions --publish   # smoke test
poetry run python run_local.py            # live: every 20 minutes
```

`main.py` without `--publish` is a dry run; `run_local.py --dry-run` loops
without publishing. Model use may incur fees.

Do not use the parent human Metaculus account token. MiniBench requires the
bot account, and only the first bot linked to a human account is prize eligible.
