# MiniBench setup

This fork targets the current MiniBench only. The scheduled workflow calls
`main.py --mode minibench --publish` every 20 minutes and skips questions the
bot has already forecast. The Metaculus Cup workflow is manual only.

The Metaculus bot account is `SoundlyLunarBot`. Its API token must be handled
by the account owner; never commit it or paste it into an issue or chat.

To activate the bot in GitHub Actions:

1. Add `METACULUS_TOKEN` as an Actions repository secret, using the bot API key
   from Metaculus Settings → My Forecasting Bots.
2. Add one model-provider key, for example `OPENROUTER_API_KEY` or
   `OPENAI_API_KEY`, as an Actions repository secret. Model use may incur fees.
3. Enable Actions for the fork, run the manual `Test Bot` workflow, and verify
   forecasts on the bot's Metaculus profile.
4. Once ready for prize participation, enable `Forecast on MiniBench questions`
   and run it manually once. Its schedule then checks for new questions.

Local invocation after installing the official Poetry dependencies:

```sh
poetry run python main.py --mode minibench
poetry run python main.py --mode minibench --publish
```

The first command is a dry run; the second publishes forecasts and comments.
Do not use the parent human Metaculus account token. MiniBench requires the
bot account, and only the first bot linked to a human account is prize eligible.
