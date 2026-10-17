<!-- Proposed post-deadline additions to the DEV post. Nothing here is published until approved. -->

<!-- 1. One line inserted directly under the "This is a submission for..." line at the top: -->

> **Note added 18 October 2026:** the "Update" section at the end of this post was added after the 11 October deadline and is not part of the judged entry. Everything else is the post as submitted.

<!-- 2. One sentence appended to the Kaggle leaderboard bullet under "My Benchmark": -->

Leaderboard rows added after 11 October are listed in the update section at the end of this post.

<!-- 3. New section appended at the very end of the post: -->

## Update: results added after the 11 October deadline (not part of the judged entry)

*Added 18 October 2026 (runs on 15 and 18 October). Same frozen task (Kaggle task version 3: same questions, prompts and scoring), run through Kaggle's task runner on the free $10/day model quota. Apart from the note at the top and one sentence on the leaderboard link, nothing above this section has changed.*

Thirteen more models, each run once:

| model | arbitrage-free, isolated | arbitrage-free, joint |
|---|---|---|
| `gpt-5.4` | 95% | 100% |
| `claude-opus-5` | 86% | 100% |
| `gpt-6-sol` | 84% | 97% |
| `gemini-4-argon` | 81% | 100% |
| `claude-opus-5-5` | 76% | 100% |
| `gpt-6.1-sol` | 78% | 100% |
| `gpt-6-astra` | 78% | 100% |
| `gpt-5.6-terra` | 78% | 100% |
| `gpt-5.6-sol` | 73% | 100% |
| `gemini-2.5-pro` | 70% | 100% |
| `claude-sonnet-4-6` | 70% | 100% |
| `gpt-6-luna` | 65% | 100% |
| `gemini-2.5-flash` | 57% | 100% |

![Post-deadline models: isolated vs joint coherence, and bookie profit by family type](https://raw.githubusercontent.com/yy5652-hash/minibench-bot/claude/gifted-cori-docto2/kaggle_benchmark/results/dutch_book_bench_update.png)

What the new runs add:

- **The isolated/joint gap holds.** All 13 are 97–100% arbitrage-free when asked a whole family at once and 57–95% when asked one statement per chat. Across all 39 models now scored: 49–95% isolated (average 72%), 95–100% joint.
- **A new top score.** `gpt-5.4` left a bookie at most 5¢ on 35 of 37 families (95%), followed by `claude-opus-5` (86%). Both are single runs, and finding 5 puts run-to-run noise at about ±8 points.
- **A caveat to finding 4.** "Newer beats bigger within a family" holds for Gemini (2.5 Flash 57% → 3.8 Flash 89%; 2.5 Pro 70% → 4 Argon 81%), but not at the top of the other two lines: `gpt-5.4` (95%) scored above `gpt-5.5` (84%), `gpt-6.1-sol` (78%) and `gpt-5.6-sol` (73%), and `claude-opus-5` (86%) above `claude-opus-5-5` (76%). With one run per model and ±8 points of noise, I would now call release generation a weak signal, not a rule.
- **Conjunctions are still where the money is.** `gemini-2.5-flash` on the earthquake family: P(California) = 0.45, P(Kanto) = 0.28, P(both) = **0.55**, P(at least one) = 0.92. "Both" is again more likely than either part: **74¢**.
- **Not scored:** `qwen3-next-80b-thinking` answered only 24% of families (it ran out of output tokens before giving a number), and `gpt-oss-120b` errored in the task runner again.

Raw replies for these runs are in the repo (`kaggle_benchmark/results/raw_runs_2026-10-15/` and `raw_runs_2026-10-18/`).
