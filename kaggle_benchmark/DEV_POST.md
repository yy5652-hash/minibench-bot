---
title: I tried to Dutch-book every LLM on Kaggle. [[N]] of [[M]] lost money to a bookie with no edge.
published: false
tags: kagglebenchmarkchallenge, devchallenge, ai, machinelearning
cover_image: [[upload dutch_book_bench.png]]
---

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23).*

<!--
HOW TO FINISH THIS DRAFT
1. Run the Kaggle notebook interactively, then paste the contents of /kaggle/working/results.md into "The numbers" below.
2. Replace every [[...]] with real values. Delete any "expected" sentence that the data doesn't support. Don't keep a claim the data doesn't show.
3. Upload dutch_book_bench.png as the cover image and as the inline chart.
-->

## TL;DR

I asked [[M]] models the same probability questions twice: once as separate questions (one per chat, the way most forecasting bots work), and once together in a single prompt. Separately, they quoted prices that a bookie could exploit: for example [[worst example, e.g. "62% that Apple out-values Microsoft and 55% that Microsoft out-values Apple"]]. Shown the questions together, the same models were [[much more / barely more]] coherent.

**Benchmark:** [[Kaggle benchmark link]] · **Notebook:** [[Kaggle notebook link]]

## Why this benchmark

I run a forecasting bot in Metaculus' AI benchmark tournament. Like most bots, it sends each question to the model in a fresh context. That made me wonder: if a question about the same event comes from two angles (*"Will X happen?"* and *"Will X **not** happen?"*), do the two answers even add up to 100%?

If they don't, the forecaster is **Dutch-bookable**. A bookie can buy and sell its contracts so that it profits **whatever happens**. De Finetti proved in the 1930s that this is exactly what it means for a set of numbers *not* to be probabilities.

The nice thing about coherence: **you don't need to know the future to measure it.** So I could ask about 2027-2050 events that no model can have memorised, and still score the answers today.

## What the benchmark tests

37 *question families*. Each family is a set of statements about the same small set of possible worlds:

| Family type | Example | Coherence rule |
|---|---|---|
| negation (6) | "Apple's market cap > Microsoft's on 29 Dec 2028" / "Microsoft's ≥ Apple's" | P(A) + P(not A) = 1 |
| threshold (5+2) | Bitcoin on 31 Dec 2028 above $50k / $100k / $150k / $250k | must not increase with the threshold. This is how Metaculus numeric CDFs are built. |
| deadline (4) | A human on Mars by 2030 / 2035 / 2040 / 2050 | must not decrease over time |
| partition (5+2) | Who wins the 2030 World Cup: Spain / France / Brazil / Argentina / England / anyone else | sums to 1 |
| conjunction (5+2) | A, B, "A and B", "A or B" | P(A∧B) ≤ min, P(A∨B) ≥ max, P(A)+P(B) = P(A∧B)+P(A∨B) |
| story (3+1) | "Cat 4-5 hurricane hits the US in 2028" vs "... and causes >$50B damage" | the detailed version can't be more likely (the Linda problem) |

28 families are about the real future. **9 are controls** (dice, coins, cards) with exact answers. The controls separate "the model can't compute probabilities" from "the model is incoherent when it's genuinely uncertain".

Every statement is asked **in isolation**, in a fresh chat. Every family is also asked **jointly**, in one prompt. That makes about 160 calls per model.

### The metric: how much money can a bookie lock in?

For each family I compute the **guaranteed profit** of a bookie who can trade at most $1 of each contract at the model's quoted prices. By LP duality, that profit equals the L1 distance from the model's answers to the nearest coherent set of probabilities. A small linear program (`scipy.optimize.linprog`) computes it exactly for any family shape. A coherent forecaster gives the bookie $0.

**Leaderboard score = arbitrage-free rate**: the % of families (asked in isolation) on which the bookie can lock in **at most 5¢**.

## Models

[[List the models, e.g. every model available in Kaggle Community Benchmarks on <date>: ...]]

## The numbers

![Coherence: isolated vs joint, and arbitrage by family type]([[chart url]])

[[PASTE results.md HERE]]

## What I learned

<!-- Below are hypotheses to CHECK against the data. Keep the ones that hold (with numbers), rewrite the ones that don't. Surprises make the best findings. -->

1. **Isolation is the problem, not ignorance.** Joint arbitrage-free rate [[X]]% vs isolated [[Y]]%. [[If true: the models "know" the rules of probability. They just don't apply them across separate calls, which is exactly how bots call them.]]
2. **Partitions are the worst offenders.** Asked one bin at a time, models give [[sum of World Cup bins, e.g. 1.6]] in total probability across six mutually exclusive outcomes. Every bin gets an "it's plausible" bump. [[check by_type table]]
3. **Controls vs the real future.** On dice and cards, arbitrage is [[A]]¢ per family. On real questions it's [[B]]¢. [[Is incoherence a math problem or an uncertainty problem?]]
4. **Bigger / reasoning models**: [[do reasoning models fix it, or just get confidently incoherent? compare]]
5. **The most expensive single answer**: [[quote the worst example from results.md, with model name and how many cents a bookie earns]].

## So what? (for anyone building forecasting bots)

- Ask related questions **together**, or post-process: project your bot's answers onto the coherent set. Because the true outcome is a vertex of that convex set, a Euclidean projection **never** makes the Brier score worse, whatever happens.
- For numeric questions, request the **whole CDF in one call** rather than threshold by threshold.
- For multiple-choice questions, ask for **all options at once** and renormalise.

## Prior work

This is in the spirit of *Consistency Checks for Language Model Forecasters* (Paleka et al.), which also uses arbitrage to score consistency. What's new here: it runs on Kaggle's model roster, it puts **exact-answer controls** next to open questions, it compares **isolated vs joint** prompting directly, and it uses one generic LP that turns any family of events into a guaranteed-profit number.

## Limitations

- Temperature 0, one sample per question. Some incoherence is sampling noise, but a bookie would happily exploit that too.
- Questions are in English, written by one person (me). A paraphrase-robustness variant is the obvious next step.
- The 5¢ tolerance is arbitrary. The mean arbitrage in cents is reported too.

Thanks to Kaggle and DEV for the challenge. Notebook, questions and code: [[links]].
