---
title: I tried to Dutch-book 13 LLM forecasters. Asked one question at a time, every one of them paid out.
published: true
tags: devchallenge, kagglechallenge, ai, machinelearning
cover_image: https://raw.githubusercontent.com/yy5652-hash/minibench-bot/claude/gifted-cori-docto2/kaggle_benchmark/results/dutch_book_bench.png
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

13 models from four providers, everything I could fit into Kaggle's $10/day model quota, cheapest and most diverse first: `gemini-3.7-flash` (the task's default model), `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite-preview`, `claude-haiku-4-5`, `claude-haiku-5-5`, `claude-opus-4-5`, `claude-opus-4-6`, `claude-opus-4-7`, `claude-opus-4-8`, `gpt-5.4-nano`, `gpt-5.4-mini`, `gpt-oss-20b`, `qwen3-235b-a22b-instruct`.

Two things worth knowing if you build on Kaggle's proxy. First, it reserves each call's worst-case cost from your quota up front, so with no `max_tokens` the biggest models refuse every concurrent call; my first run silently turned those refusals into "incoherent" scores. The benchmark now caps `max_tokens`, retries, records API errors, and refuses to score a model with low coverage. Second, thinking tokens are what make a 160-call suite expensive, so day-2 models were run with `reasoning="low"`; the seven day-1 models ran at their defaults. `glm-5` returned empty replies on half the questions and was not scored; `gemma-4` and `grok-4.20` were skipped because of a parameter mismatch I found too late. They go in the next run.

## Findings

![Isolated vs joint coherence per model, and where the bookie's profit comes from](https://raw.githubusercontent.com/yy5652-hash/minibench-bot/claude/gifted-cori-docto2/kaggle_benchmark/results/dutch_book_bench.png)

**1. Every model knows the rules of probability. It just doesn't apply them across separate calls.**
On the 9 dice-and-card controls, all 13 models are essentially perfectly coherent (≤ 1¢ per family, Brier ≈ 0). Asked a whole family in one prompt, they are 95–100% arbitrage-free. Asked one statement per chat, they drop to **49–84%**. The problem is not ignorance; it is isolation, which is exactly how forecasting bots call these models.

**2. The money is in conjunctions, partitions and negations. Monotone families are nearly free.**
Across all models and families asked in isolation:

| family type | arbitrage-free rate (isolated) |
|---|---|
| conjunction | 49% |
| partition | 48% |
| negation | 60% |
| threshold | 91% |
| deadline | 92% |
| story | 96% |

Deadlines ("by 2030 / 2035 / 2040") and thresholds ("above $50k / $100k / …") are mostly fine: models handle *monotone* structure even across calls. The three family types with a *conservation law* (things must add up) are where the bookie eats. The worst single family was the earthquake conjunction (29.5¢ per model on average), the best was anything with a date ladder.

**3. The most expensive single answers.** A bookie earns these with zero information:
- `qwen3-235b`, earthquake conjunction: P(M7+ in California by 2035) = **0.18**, P(M7+ in Kanto) = **0.35**, P(both) = **0.75**, P(at least one) = **0.98**. "Both" is more likely than either part. Worth **$1.20** per $1 of contracts, the maximum this benchmark can award.
- `gpt-oss-20b`, same family: P(California) = **0.995**, P(Kanto) = **0.015**, P(both) = **0.9996**. **$1.08**.
- `gpt-5.4-mini`, the Moon: P(someone walks on the Moon before 2029) = **0.74** and P(nobody does) = **0.74**. They sum to **1.48**. `gpt-5.4-nano` did the same (1.43). The model agrees with whichever framing it is shown.
- `claude-opus-4-7`, climate conjunction: P(A) = 0.35, P(B) = 0.38, P(both) = 0.28, P(at least one) = **0.90**. **45¢**.
- "Which of 2027–2030 will be the warmest year", four mutually exclusive answers: `qwen3-235b` 1.37, `haiku-4-5` 1.32, `gpt-5.4-mini` 1.31. The 2030 World Cup partition goes the other way for `gpt-oss-20b`: six exhaustive outcomes that sum to **0.36**.

**4. The best model was the cheapest one, and price barely predicts coherence.** `gemini-3.7-flash` (2.0¢/family) beat every Claude Opus (3.9–5.4¢). `gemini-3.1-flash-lite-preview`, a lite model, tied `claude-haiku-5-5` at 78%. The one clear pattern is at the bottom: the two open-weight models (`gpt-oss-20b`, `qwen3-235b`) are the most Dutch-bookable, almost entirely because of conjunctions (41¢ and 29¢ per family).

**5. Temperature 0 is not deterministic on this proxy.** The default model scored 67.6%, 75.7% and 83.8% on three identical runs. A single-run leaderboard number carries roughly ±8 points of noise, so I report family-level cents alongside the headline percentage and treat differences under ~10 points as a tie.

**6. The Linda problem is mostly solved.** Adding a plausible detail ("…aboard a SpaceX Starship") almost never raised the probability (story families 96% arbitrage-free).

### What I'd measure next
- Paraphrase robustness: the negation failures look like an *acquiescence* effect, so ask the same family as "Will X happen?" vs "Is it false that X happens?".
- Whether sampling 5 answers and averaging recovers coherence (it should reduce the run-to-run noise in finding 5, but not the systematic conjunction errors).
- Resolved questions, in a year: does coherence predict accuracy?

### If you build forecasting bots
- For multiple-choice and numeric questions, ask for **all options / the whole CDF in one call** and renormalise.
- For anything else, **project your answers onto the coherent set** after the fact. Because the true outcome is a vertex of that convex set, the projection can never make the Brier score worse, whatever happens. The LP in the notebook does it.

## My Benchmark

- Kaggle benchmark (leaderboard): https://www.kaggle.com/benchmarks/yy5652/dutch-book-bench — the leaderboard column is a fresh batch run of the task per model (a subset of the 13 models above, re-run through Kaggle's own task runner, so the numbers differ by the ±8-point run-to-run noise described in finding 5)
- Kaggle task page (code, per-model outputs, the model's own reaction to its worst Dutch book): https://www.kaggle.com/benchmarks/tasks/yy5652/dutch-book-bench
- Source, offline test and results: https://github.com/yy5652-hash/minibench-bot/tree/claude/gifted-cori-docto2/kaggle_benchmark

Prior work: *Consistency Checks for Language Model Forecasters* (Paleka et al.) also uses arbitrage to score consistency. What's different here: exact-answer controls next to open questions, a direct isolated-vs-joint comparison, one generic LP that turns any family of events into a guaranteed-profit number, and Kaggle's model roster.
