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
| 8 | 1:25 | Black. One number lands: **[+X.X]%**. Small label under it. | Rolling backtest on real Walmart sales: forecast value add, calibrated agent vs calibrated baseline. | Real Walmart sales. 60 products. 26 weeks. | "Does it pay? We replayed half a year of real Walmart sales. Every week forecast only from the past." |
| 9 | 1:38 | Same layout, next number: **[−Z.Z]%**. | Inventory cost: the real cost of leftovers and lost sales when ordering with each forecast. | Inventory cost, [−Z.Z]%. | "Leftovers and lost sales, counted against what actually sold: [Z] percent cheaper." |
| 10 | 1:48 | Same layout, last number: **[+W.W]%**, label "vs a classical uplift model". | The ablation: what the model's judgment adds over a rule using the same evidence. | Judgment, measured. | "And against a classical model using the very same evidence, the judgment still adds [W] percent." |
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
