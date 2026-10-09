---
title: My forecasting bot kept answering the headline, so I benchmarked whether LLMs read the fine print
published: false
tags: devchallenge, kagglechallenge, ai, machinelearning
---

<!--
BEFORE PUBLISHING
1. Start the post from the "Submit" button on https://dev.to/challenges/kaggle-2026-09-23 so it
   gets the official template + tags; paste these sections into it.
2. Replace every [[...]] with real numbers from the notebook output. Do not guess numbers.
3. Delete this comment.
-->

*This is a submission for the [Kaggle Benchmarking Challenge](https://dev.to/challenges/kaggle-2026-09-23).*

## The failure that started this

I run a small forecasting bot in Metaculus' MiniBench, an AI forecasting tournament. Reading its losses, the same pattern kept showing up. The bot's research was fine: it found the right news. Then it forecast the *headline* of the question instead of the *resolution criteria*.

Real forecasting questions are decided by their fine print, for example:

- "...according to the **first** published estimate. Later revisions are ignored."
- "...before October 1, 00:00 **UTC**."
- "...on the **last trading day** of September", not "at any time".
- "...as **certified** by the electoral commission", not as projected by networks.

A human superforecaster reads that line twice. I wanted to know how often a model doesn't read it at all.

## What I built: Fine Print, a minimal-pair benchmark

**Kaggle benchmark:** [[LINK TO KAGGLE BENCHMARK]]

Fine Print is **40 minimal pairs (80 questions)**. Both questions in a pair have:

- the **same headline**
- the **same confirmed facts** (the "latest news")
- the **same date**, after everything relevant has already happened

They differ in exactly **one clause of the resolution criteria**, and that clause flips the correct answer.

| | Control version | Trap version |
|---|---|---|
| Headline | Will Northvale's Q2 GDP growth exceed 2.0%? | *same* |
| Facts | Advance estimate 2.3% ("a strong quarter"), revised to 1.9%, then 1.8% | *same* |
| Criteria | ...the **advance (first)** estimate... | ...the **most recent** estimate available on Oct 1... |
| Correct answer | YES | NO |

There are eight trap families, five pairs each:

| Family | The clause that matters |
|---|---|
| `data_vintage` | first release vs. revised/final figure |
| `threshold_rounding` | ≥ vs. >, rounded vs. unrounded, percent vs. percentage points |
| `deadline_timezone` | local time vs. UTC, or the question's close date |
| `announced_vs_effective` | signed/approved vs. in force/sworn in/closed |
| `status_vs_ever` | "at any time" vs. "on the resolution date", intraday vs. close |
| `definition_scope` | which entities, stations, or flights count |
| `counting_rules` | attempts vs. successes, single vs. cumulative, extra time |
| `resolution_source` | ministry vs. agency, official chart vs. streaming chart |

### Design choices

- **All entities are fictional.** Northvale, Kestrel Motors and Aurelia Coin don't exist, so a model can't answer from memory. It has to read.
- **Every question is already decided.** The prompt says the facts are confirmed and complete. The right forecast is near 0 or 1, so there is no "it's uncertain" excuse.
- **Labels are balanced.** Exactly 50% of items resolve YES, and traps flip in both directions, so a model that always says NO gains nothing.
- **"Control" means the fine print agrees with the plainest reading of the headline** and of the most prominent news line. The trap is where the criteria quietly override it.

### Scoring

The model must end its answer with `PROBABILITY: <0-1>`. The main leaderboard metric is **pair accuracy**: the share of pairs where *both* versions land on the correct side of 50%.

- A model that **ignores the fine print** gives the same answer to both versions. It scores **0%** on pair accuracy, even though it gets 50% of individual questions right.
- A **coin flip** scores **25%**.
- A careful reader scores **100%**.

The notebook also reports Brier score, control vs. trap accuracy, and a **confidently wrong** rate: items where the model put ≥90% on the wrong answer. That last number is the one that hurts in a log-scored tournament.

Everything is built with the `kaggle-benchmarks` SDK. A per-question sub-task (`store_task=False`) runs through `.evaluate()` over the item DataFrame, and the parent task returns pair accuracy for the leaderboard. Unparseable answers are scored as 0.5, which counts as wrong.

## Models tested and why

[[List the models from "Evaluate More Models" and say why each was chosen. Suggested mix: a frontier reasoning model, a fast/cheap model of the kind most tournament bots actually run on because of cost, an open-weights model, and a small model. The question for bot builders is whether the cheap model is safe to use.]]

## Results

[[PASTE: the leaderboard table, i.e. pair accuracy per model]]

[[PASTE: the summary table printed by the analysis cell (pair / control / trap accuracy, Brier, confidently wrong)]]

[[PASTE: the per-family table]]

## What I learned

<!-- Write these only from your actual numbers. The prompts below are things to look for in the
     output. They are not findings. Delete any that your data doesn't support. -->

1. **The control/trap gap.** [[How much lower is trap accuracy than control accuracy? If the gap is large, models default to the headline reading.]]
2. **Which clause is hardest.** [[Which family has the lowest accuracy? Is it the same across models?]]
3. **Confidence when wrong.** [[What share of wrong answers were ≥90% confident? For a forecasting bot this matters more than accuracy.]]
4. **Fine-print-blind pairs.** [[The share of pairs where a model gave the same answer to both versions, i.e. didn't react to the clause at all.]]
5. **Does "quote the clause first" fix it?** [[Compare plain vs. quote_first. Did pair accuracy go up? For which families? This is a one-line change any bot builder can make.]]

## What I'm changing in my bot

[[Based on the ablation, e.g. "my bot's prompt now makes the model quote the deciding clause before forecasting", or "I switched models for the final forecasting step". Only claim what you actually changed.]]

## Try it / extend it

The notebook is public: [[LINK TO KAGGLE NOTEBOOK]]. Adding a pair takes one dict: a headline, the facts, and two criteria that differ by one clause. If you've seen a question that tripped your own bot, send it my way. The best trap pairs come from real losses.
