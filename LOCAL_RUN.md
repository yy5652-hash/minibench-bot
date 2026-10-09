# 在自己电脑上运行 / Running on your computer

所有运行都在你自己的电脑上做；GitHub Actions 不再自动运行（只保留手动按钮作备用）。
All runs happen on your own computer. GitHub Actions no longer runs on a
schedule; its workflows are manual-only fallbacks.

## 1. 一次性准备 / One-time setup

需要 Python 3.11+ 和 Poetry。Needs Python 3.11+ and Poetry.

```sh
git clone https://github.com/yy5652-hash/minibench-bot.git
cd minibench-bot
poetry install
cp .env.template .env        # Windows: copy .env.template .env
```

用文本编辑器打开 `.env`，填入 `METACULUS_TOKEN`（SoundlyLunarBot 的 bot token）和一个模型 key
（如 `OPENROUTER_API_KEY`）。`.env` 已被 git 忽略，不要提交。
Open `.env` and fill in `METACULUS_TOKEN` (the SoundlyLunarBot bot token) and
one model key such as `OPENROUTER_API_KEY`. `.env` is git-ignored; never commit it.

## 2. 测试 / Test

```sh
poetry run python main.py --mode test_questions              # dry run, publishes nothing
poetry run python main.py --mode test_questions --publish    # posts to bot-testing-area
```

## 3. 正式运行（替代每 20 分钟的 GitHub 定时）/ Live runs

```sh
poetry run python run_local.py
```

每 20 分钟预测一次 Fall FutureEval 2026 + MiniBench 的新问题并发布，日志在 `logs/`。
按 Ctrl+C 停止。电脑关机或睡眠时不会运行，请保持开机并关闭自动睡眠。
Forecasts new Fall FutureEval 2026 + MiniBench questions every 20 minutes and
publishes them; logs go to `logs/`. Ctrl+C stops it. Nothing runs while the
computer is off or asleep, so keep it awake.

常用选项 / Options:

```sh
poetry run python run_local.py --once                # 只跑一次 / one pass
poetry run python run_local.py --dry-run             # 不发布 / don't publish
poetry run python run_local.py --mode minibench      # 只跑 MiniBench
poetry run python run_local.py --interval-minutes 30
```

同一时间只能运行一个 `run_local.py`，第二个会直接退出。
Only one `run_local.py` can run at a time; a second copy exits immediately.

### 关掉终端后继续运行 / Keep it running after closing the terminal

macOS / Linux:

```sh
mkdir -p logs && nohup poetry run python run_local.py > logs/run_local.out 2>&1 &
```

Windows (PowerShell):

```powershell
Start-Process -WindowStyle Hidden poetry -ArgumentList "run","python","run_local.py"
```

## 4. 其他命令 / Other commands

```sh
poetry run python main.py --mode metaculus_cup --publish     # Metaculus Cup
poetry install --with integrations                           # bot-review, once
poetry run bot-review review --resolved-since 30 --output review.json --summary review.md
```

## 例外 / Exceptions

只有当主办方（Metaculus）的比赛规则要求某个步骤在别处运行时，才改用其他方式。
目前 FutureEval 和 MiniBench 都不要求用 GitHub Actions。
Only move a step off this computer if the host's (Metaculus) tournament rules
require it. FutureEval and MiniBench currently do not require GitHub Actions.
