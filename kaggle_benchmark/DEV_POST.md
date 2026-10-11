---
title: I tried to Dutch-book 26 LLM forecasters. Asked one question at a time, every one of them paid out.
published: true
tags: devchallenge, kagglechallenge, ai, machinelearning
cover_image: https://raw.githubusercontent.com/yy5652-hash/minibench-bot/claude/gifted-cori-docto2/kaggle_benchmark/results/dutch_book_bench_26.png
---

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23).*

## What I Benchmarked

I run a bot in Metaculus' AI forecasting tournament. Like almost every forecasting bot, it sends each question to the model **in a fresh chat**. That made me wonder: when the same event shows up from two angles, *"Will the US unemployment rate be 5% or higher in December 2027?"* and *"Will it be below 5%?"*, do the two answers even add up to 100%?

If they don't, the forecaster is **Dutch-bookable**. A bookie can buy and sell its contracts so that it profits **whatever happens**. De Finetti showed in the 1930s that this is exactly what it means for a set of numbers to not be probabilities.

The useful property of coherence: **you don't need to know the future to measure it.** So the benchmark asks about 2027–2050 events that no model can have memorised, and still scores the answers today.

### The 37 question families

Each family is a set of statements about the same small set of possible worlds:

| Family type | Example | Coherence rule |
|---|---|---|
| negation (6) | "Apple's market cap > Microsoft's on 29 Dec 2028" / "Microsoft's ≥ Apple's" | P(A) + P(not A) = 1 |
| threshold (5) | Bitcoin on 31 Dec 2028 above $50k / $100k / $150k / $250k | must not increase with the threshold; this is how Metaculus builds numeric CDFs |
| deadline (4) | A human on Mars by 2030 / 2035 / 2040 / 2050 | must not decrease over time |
| partition (5) | Who wins the 2030 World Cup: Spain / France / Brazil / Argentina / England / anyone else | sums to 1 |
| conjunction (5) | A, B, "A and B", "A or B" | P(A∧B) ≤ min, P(A∨B) ≥ max, P(A) + P(B) = P(A∧B) + P(A∨B) |
| story (3) | "A Cat 4–5 hurricane hits the US in 2028" vs "…and causes >$50B damage" | the detailed version can't be more likely (the Linda problem) |

28 families are about the real future. **9 are controls** (dice, coins, cards) with exact answers. The controls separate "can't compute probabilities" from "is incoherent when genuinely uncertain".

Every statement is asked **in isolation**, in a fresh chat, the way bots do it. Every family is also asked **jointly**, in one prompt. About 160 calls per model, temperature 0.

### The metric: how much money can a bookie lock in?

For each family I compute the **guaranteed profit** of a bookie who can trade at most $1 of each contract at the model's quoted prices. By LP duality this equals the L1 distance from the model's answers to the nearest coherent set of probabilities; a small exact solver computes it for any family shape. A coherent forecaster gives the bookie $0.

**Leaderboard score = arbitrage-free rate**: the % of families (asked in isolation) on which the bookie can lock in **at most 5¢**. A model that fails to answer 10% or more of the families (API errors, no parseable number) is not scored at all, so a dropped call never counts as incoherence.

## Models Tested

26 models from six providers (Google, Anthropic, OpenAI, xAI, Alibaba, plus open-weight releases), everything I could fit into Kaggle's $10/day model quota over three days:

- **Google:** `gemini-3.8-flash`, `gemini-3.7-flash` (the task's default model), `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite-preview`, `gemini-3-flash-preview`, `gemini-3.1-pro-preview`, `gemma-4-31b`
- **Anthropic:** `claude-haiku-4-5`, `claude-haiku-5-5`, `claude-sonnet-5`, `claude-sonnet-5-5`, `claude-opus-4-5`, `claude-opus-4-6`, `claude-opus-4-7`, `claude-opus-4-8`
- **OpenAI:** `gpt-5.4-nano`, `gpt-5.4-mini`, `gpt-5.5`, `gpt-5.6-luna`, `gpt-oss-20b`
- **xAI / Alibaba:** `grok-4.20` (non-reasoning), `qwen3-235b`, `qwen3-next-80b`, `qwen3-coder-480b`

Three things worth knowing if you build on Kaggle's proxy. First, it reserves each call's worst-case cost from your quota up front, so with no `max_tokens` the biggest models refuse every concurrent call; my first run silently turned those refusals into "incoherent" scores. The benchmark now caps `max_tokens`, retries, records API errors, and refuses to score a model with low coverage. Second, thinking tokens are what make a 160-call suite expensive, so everything after day 1 ran with `reasoning="low"` where the model accepts it; the seven day-1 models ran at their defaults. Third, check your parser against the controls: several models answer dice questions as fractions ("Probability: 11/36"), and my parser read that as 0.11. I found it on the last day, fixed it, and re-scored the affected runs from their saved raw replies. It moved two models by one family each.

Not scored: `glm-5` (empty replies on half the questions), `deepseek-r1` and `gemma-4-26b` (ran out of output tokens before giving a number on 40–50% of families), `gpt-oss-120b` (the runner errored), and `grok-4.5` / `grok-4.6` (listed, but the proxy answers 404).

## Findings

![Isolated vs joint coherence per model, and where the bookie's profit comes from](https://raw.githubusercontent.com/yy5652-hash/minibench-bot/claude/gifted-cori-docto2/kaggle_benchmark/results/dutch_book_bench_26.png)

**1. Every model knows the rules of probability. It just doesn't apply them across separate calls.**
On the 9 dice-and-card controls, 23 of the 26 models are essentially perfectly coherent (≤ 1¢ per family). Asked a whole family in one prompt, every model is 95–100% arbitrage-free, and 21 of 26 score a clean 100%. Asked one statement per chat, they drop to **49–89%**, 70% on average. The problem is not ignorance; it is isolation, which is exactly how forecasting bots call these models.

**2. The money is in conjunctions, partitions and negations. Monotone families are nearly free.**
Across all models and families asked in isolation:

| family type | arbitrage-free rate (isolated) |
|---|---|
| conjunction | 49% |
| partition | 52% |
| negation | 57% |
| deadline | 93% |
| threshold | 94% |
| story | 95% |

Deadlines ("by 2030 / 2035 / 2040") and thresholds ("above $50k / $100k / …") are mostly fine: models handle *monotone* structure even across calls. The three family types with a *conservation law* (things must add up) are where the bookie eats. The worst single family was the earthquake conjunction (26¢ per model on average), the best was anything with a date ladder.

**3. The most expensive single answers.** A bookie earns these with zero information:
- `qwen3-235b`, earthquake conjunction: P(M7+ in California by 2035) = **0.18**, P(M7+ in Kanto) = **0.35**, P(both) = **0.75**, P(at least one) = **0.98**. "Both" is more likely than either part. Worth **$1.20** per $1 of contracts, the maximum this benchmark can award.
- `gpt-oss-20b`, same family: P(California) = **0.995**, P(Kanto) = **0.015**, P(both) = **0.9996**. **$1.08**.
- `qwen3-next-80b`, two IPOs: P(OpenAI lists) = **0.40**, P(SpaceX lists) = **0.85**, P(both) = **0.10**, P(at least one) = **0.15**. "At least one" is less likely than either. **$1.00**.
- `grok-4.20` (non-reasoning), on a *control*: asked for P(at least two of five dealt cards share a rank), it reasoned that there are "13 ranks and only 4 suits, so by the pigeonhole principle" five distinct ranks are impossible, and answered **1**. In the next chat it computed P(all five ranks differ) = **0.507**, correctly. **51¢**, on a question with a textbook answer.
- `gpt-5.4-mini`, the Moon: P(someone walks on the Moon before 2029) = **0.74** and P(nobody does) = **0.74**. They sum to **1.48**. `gpt-5.4-nano` did the same (1.43), and `qwen3-next-80b` went to 1.80 (0.95 and 0.85). The model agrees with whichever framing it is shown.
- `claude-opus-4-7`, climate conjunction: P(A) = 0.35, P(B) = 0.38, P(both) = 0.28, P(at least one) = **0.90**. **45¢**.
- "Which of 2027–2030 will be the warmest year", four mutually exclusive answers: `qwen3-235b` 1.37, `haiku-4-5` 1.32, `gpt-5.4-mini` 1.31. The 2030 World Cup partition goes the other way for `gpt-oss-20b`: six exhaustive outcomes that sum to **0.36**.

**4. Newer beats bigger. Price barely predicts coherence.** The top three are `gemini-3.8-flash` (89%), `gpt-5.5` and `gemini-3.7-flash` (both 84%). `gemini-3.1-pro-preview` (68%) sits below six Flash and Flash-Lite models from its own family, and every Claude Opus (68–76%) is at or below `claude-haiku-5-5` (78%). What does track coherence is the release generation inside a family: Gemini Flash goes 68 → 78 → 76 → 84 → 89 from 3.0 to 3.8, Haiku 65 → 78 and Sonnet 68 → 76 from one release to the next, GPT 59 (5.4-mini) → 84 (5.5). At the bottom, four of the eight lowest scores are open-weight models (`gpt-oss-20b`, `qwen3-coder-480b`, `qwen3-next-80b`, `qwen3-235b`), almost entirely because of conjunctions (20–41¢ per family).

**5. Temperature 0 is not deterministic on this proxy.** The default model scored 67.6%, 75.7%, 81.1% and 83.8% on four identical runs. A single-run leaderboard number carries roughly ±8 points of noise, so I report family-level cents alongside the headline percentage and treat differences under ~10 points as a tie.

**6. The Linda problem is mostly solved.** Adding a plausible detail ("…aboard a SpaceX Starship") almost never raised the probability (story families 95% arbitrage-free).

### What I'd measure next
- Paraphrase robustness: the negation failures look like an *acquiescence* effect, so ask the same family as "Will X happen?" vs "Is it false that X happens?".
- Whether sampling 5 answers and averaging recovers coherence (it should reduce the run-to-run noise in finding 5, but not the systematic conjunction errors).
- Resolved questions, in a year: does coherence predict accuracy?

### If you build forecasting bots
- For multiple-choice and numeric questions, ask for **all options / the whole CDF in one call** and renormalise.
- For anything else, **project your answers onto the coherent set** after the fact. Because the true outcome is a vertex of that convex set, the projection can never make the Brier score worse, whatever happens. The LP in the notebook does it.

## My Benchmark

- Kaggle benchmark (leaderboard): https://www.kaggle.com/benchmarks/yy5652/dutch-book-bench — the leaderboard column is a batch run of the task per model through Kaggle's own task runner. For the 13 models I added on the last day it is the same run as in the chart; for the earlier ones it is a re-run, so the numbers differ by the ±8-point noise described in finding 5
- Kaggle task page (code, per-model outputs, the model's own reaction to its worst Dutch book): https://www.kaggle.com/benchmarks/tasks/yy5652/dutch-book-bench
- Source, offline test and results: https://github.com/yy5652-hash/minibench-bot/tree/claude/gifted-cori-docto2/kaggle_benchmark

Prior work: *Consistency Checks for Language Model Forecasters* (Paleka et al.) also uses arbitrage to score consistency. What's different here: exact-answer controls next to open questions, a direct isolated-vs-joint comparison, one generic LP that turns any family of events into a guaranteed-profit number, and Kaggle's model roster.
