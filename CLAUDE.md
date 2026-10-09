# Project rules

## Everything runs on the owner's computer

The owner runs this bot and every command on their own computer, not in the
cloud. Apply this to all current and future work:

- Give run, test, install and review instructions as commands for the owner's
  local terminal (`poetry run ...`, `run_local.py`). See `LOCAL_RUN.md`.
- Do not add GitHub Actions `schedule:` triggers, cloud cron jobs, or other
  hosted runners. Existing workflows stay `workflow_dispatch` only.
- Secrets live in the local, git-ignored `.env`, never in the repo.
- The only exception is a requirement in the host tournament's (Metaculus)
  rules. If one applies, say which rule requires it before adding a cloud step.
