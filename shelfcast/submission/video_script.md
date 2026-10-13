# Demo video: storyboard (about 2:30)

Written to the keynote standard: one subject per shot, a single wow moment, and every shot shows a
real capability. Replace each `[...]` with the number on screen or in `results/*.md`; never invent one.
Record the product shots live on the MI300X so the latency and "on the GPU" labels are real.

## (a) Visual rules

- **Canvas:** near-black background (`#0f1216`), the dashboard in its dark theme. One accent colour
  only: the ShelfCast teal. The baseline is always grey. No gradients, no stock footage, no icons.
- **One subject per shot:** a single number, a single chart, or a single sentence. Everything else is
  cropped out or dimmed to 20%.
- **Type:** one sans-serif family. Big numbers at about 1/6 of frame height; captions small, lower
  left, sentence case, at most seven words.
- **Motion:** slow push-ins (2-3% over the shot) and hard cuts. A number may count up once, in the
  wow shot only. No spins, no bounces, no transitions with names.
- **Sound:** a low, sparse pad under the opening; **full silence** for one beat before the wow
  number lands; one soft tone when it lands. Voice is calm, unhurried, never salesy.
- **Screen capture:** 1920x1080, browser chrome hidden, cursor hidden except in shot 6 where typing
  is the point.

## (b) Arc

Quiet problem (0:00-0:20) → the system's blind spot made visible (0:20-0:40) → **wow: the order
changes from 21 to 41** (0:40-1:00) → proof it reads what a person knows (1:00-1:25) → proof it pays,
on real sales (1:25-2:00) → the machine underneath (2:00-2:20) → one line, out (2:20-2:30).

## (c) Shots

| # | Time | On screen (one subject) | Capability shown | Caption (exact) | Voice-over (exact) |
|---|---|---|---|---|---|
| 1 | 0:00 | Black. One line of white text fades in. | None: the problem. | How many should we order? | "Every week, every store, every product: someone has to answer this." |
| 2 | 0:08 | The same line. Two short words appear beneath it, left and right: "Too few." "Too many." | None: the stakes. | Empty shelf. Or waste. | "Too few is an empty shelf. Too many is waste." |
| 3 | 0:20 | The sales chart alone: 26 weeks of Canned Pumpkin, then the grey baseline bar for Thanksgiving week. Slow push-in on the grey bar. | The statistical baseline: what replenishment systems forecast today. | The system forecast: 21. | "This is what a replenishment system sees. It extrapolates last month. It has no idea next week is Thanksgiving." |
| 4 | 0:36 | Hold on the grey bar. Music drops out. One beat of silence. | (Setup for the wow.) | (none) | (silence) |
| 5 | 0:40 | **Wow.** The teal bar rises beside the grey one. Cut to the order tile alone on black: the number counts once from 21 to **[41]**. One soft tone. | The agent's forecast becomes an order at the cost-optimal quantile. | Order [41], not 21. | "ShelfCast read the calendar. In both past Thanksgivings this product sold [2.7] times what that same forecast predicted. So it orders [41]." |
| 6 | 1:00 | The drivers list, one row: "+[82]% Thanksgiving", with its evidence line. | Every adjustment names its driver and its evidence. | Every change has a reason. | "It tells you why. Each driver, with the evidence behind it." |
| 7 | 1:10 | The notes box. The cursor types: "Store closed Monday for renovation". Cut to the order tile dropping to **[N]**. | Free-text planner notes change the plan; no statistical model can read them. | It reads what you know. | "And it listens. Tell it what the sales history can't know, and the plan changes." |
| 8 | 1:25 | Black. One number lands: **[−X.X]%**. Small label under it. | The decision layer on real Walmart sales (M5): ordering the cost-optimal quantile instead of the point forecast. No model involved. | Real Walmart sales. [N] products. [W] weeks. | "Does it pay? We replayed real Walmart sales, every week forecast only from the past. Ordering the right quantile instead of the forecast itself cuts inventory cost by [X] percent." |
| 9 | 1:38 | Same layout, next number: **[−Z.Z]%**. | Planner-notes experiment (synthetic store): inventory cost in weeks where the planner left a free-text note. | It reads what you know. | "When a planner writes down what they know, in plain words and with no number, the order follows: [Z] percent cheaper in those weeks." |
| 10 | 1:48 | Same layout, last number: **[+W.W]%**, label "accuracy over a model with no LLM". | The ablation: the same evidence and the same weeks, with and without the language model. | Judgment, measured. | "And against a classical model given the very same evidence, the judgment adds [W] percent. Only one of them can read." |
| 11 | 2:00 | A terminal, full frame, dark: `amd-smi` showing one MI300X at load. Then one number on black: **[N] forecasts a minute**. | Inference on one AMD Instinct MI300X with vLLM on ROCm; throughput from the benchmark. | One AMD Instinct MI300X. | "All of it runs on one AMD Instinct MI300X. An open model, served by vLLM on ROCm. [N] forecasts a minute, at [$X] per thousand." |
| 12 | 2:12 | One line on black. | Open weights on the retailer's own GPU: sales data never leaves. | Your model. Your GPU. Your data. | "Open weights, your own GPU. The sales data never leaves the building." |
| 13 | 2:20 | The word **ShelfCast**, then the repo and demo URLs beneath it. Hold two seconds. Cut to black. | (Close.) | From forecast to the right order. | "ShelfCast. From forecast to the right order. On AMD." |

## Self-check against the standard

1. **A useful work of art.** Every shot has exactly one subject; shots 8-10 are a single number each.
   One accent colour, one typeface, push-ins and hard cuts only. Nothing decorative.
2. **It lands.** Calm open, a full beat of silence at 0:36, then the one moment the film is built
   around: 21 becomes 41. Proof follows in three single-number shots; the close is one line.
3. **It explains the product.** A viewer leaves knowing: it forecasts demand and turns the forecast
   into an order (3-5), explains itself (6), takes a planner's notes (7), is measured on real sales
   and against a no-LLM model (8-10), and runs on one AMD GPU with open weights (11-12). The
   forecasting method is stated on screen and in voice, as the track brief requires: a statistical
   forecast, adjusted by the model, never the model alone.

Open risk: shots 8-10 only work if the real numbers are good. If one is weak, cut that shot rather
than soften the caption; do not swap in a number from the synthetic store without labelling it.

## Tooling: reuse before building

Searched GitHub on 10 Oct 2026 for something to reuse rather than hand-rolling a render pipeline.
Nothing was found that is an Apple-keynote product-video template with real adoption; the popular,
reusable pieces are the engines. Shortlist, by stars and licence:

| Repository | Stars | Licence | Verdict |
|---|---:|---|---|
| `motion-canvas/motion-canvas` | 19k | MIT | **Use this.** Code-driven scenes, precise type and timing, MIT like this project. |
| `midrender/revideo` | 4k | MIT | Motion Canvas fork with headless rendering. Use if we need to render without the editor. |
| `motion-canvas/examples` | 1.2k | MIT | Starting scenes to adapt (text reveals, number tweens, chart builds). |
| `remotion-dev/remotion` | 63k | Remotion licence (free for individuals, not MIT) | Most capable, but its licence is not MIT; keep it out of a repository the rules require to be MIT-compliant. |
| `zz41354899/SwiftClip` | 44 | MIT | Storyboard-driven Remotion templates; small, and inherits the Remotion licence question. |
| `calesthio/OpenMontage` | 66k | AGPL-3.0 | Agentic video production system. AGPL: do not vendor. |

Plan: screen-record shots 3, 5-7 and 11 from the live dashboard and terminal (they must be real).

What was built, and why it differs from the shortlist: the type-on-black shots (1, 2, 4, 8-10, 12, 13)
are rendered by `submission/build_video_cards.py`. Motion Canvas needs Node.js, which is not installed on
the build machine, and these shots are a line of type or one number with a slow push-in, so the script
uses plain HTML and CSS recorded with Playwright's Chromium (Apache-2.0) and encoded with ffmpeg through
`imageio-ffmpeg` (BSD-2-Clause). Nothing was vendored from another repository. It reuses the deck's
palette and type, takes every number from `results/`, and skips a number shot when its result is
missing rather than render a placeholder.

    pip install playwright imageio-ffmpeg && playwright install chromium
    python submission/build_video_cards.py --results results --out submission/video

Shots 8-10 changed after the rehearsal with the real model: on anonymised Walmart items the model adds
nothing over the baseline, so shot 8 now shows the decision layer on real sales, and shots 9-10 show the
planner-notes experiment, where the model's own contribution is measured.
