#!/bin/zsh
# One pass of the local runner; launchd starts it every five minutes.
# Without the token or the model service it exits, and the hosted backup covers the question.
cd "${0:A:h}/.." || exit 1
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

mkdir -p .data/local-forecasts
if [ -f .data/local-runner.log ] && [ "$(stat -f%z .data/local-runner.log)" -gt 5000000 ]; then
  tail -c 1000000 .data/local-runner.log > .data/local-runner.log.tmp && mv .data/local-runner.log.tmp .data/local-runner.log
fi

METACULUS_TOKEN="$(security find-generic-password -s metaculus-bot-token -a SoundlyLunarBot -w 2>/dev/null)"
if [ -z "$METACULUS_TOKEN" ]; then
  echo "$(date -u +%FT%TZ) no bot token in the keychain; the hosted backup covers this pass"
  exit 0
fi
export METACULUS_TOKEN

export LOCAL_MODEL_BASE_URL="http://127.0.0.1:10100/v1"
export RESEARCH_MODEL="${RESEARCH_MODEL:-claude/claude-sonnet-5-5,codex/gpt-6.1-sol}"
export FORECAST_MODEL="${FORECAST_MODEL:-claude-cli/claude-opus-5-5,codex/gpt-6.1-sol,claude-cli/claude-sonnet-5-5,deepseek/deepseek-flash}"
export PARSER_MODEL="${PARSER_MODEL:-deepseek/deepseek-flash}"
# The hosted backup takes questions closing within 75 minutes, so stop just before that.
export ONLY_CLOSING_AFTER_MINUTES=80

exec .venv/bin/python main.py --mode tournament --publish --predictions "${PREDICTIONS_PER_QUESTION:-4}" \
  --output-dir .data/local-forecasts
