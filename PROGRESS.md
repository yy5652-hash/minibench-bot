# FutureEval bot progress

## Current state (2026-11-01)
- Bot account: SoundlyLunarBot (309116). Tournaments: Fall 2026 FutureEval (ends 2027-01-06) and MiniBench.
- Rules that shape the design: one forecast per question; only the last forecast before close is scored; a missed question scores 0; no testing on open tournament questions.
- Hosted runner (GitHub Actions) is live on the new pipeline with free Gemini models, stepping down to flash-lite when a daily quota is spent.
- Local runner (`scripts/run_local.sh`, launchd) is written and tested on closed questions. It waits for the bot token in the macOS keychain.

## Next
- When the token is stored: check it, set `ONLY_CLOSING_WITHIN_MINUTES=75`, restart the hosted workflow, load the launchd agent.
- Re-score once more questions resolve: compare per-model results from the private comments.
- Optional: AskNews free tier (needs an email from the owner), PCHIP numeric smoothing, Platt scaling after a few hundred resolved forecasts.

## Experiments
Baseline source: No-Stream/metaculus-bot (MIT), 15th of 277 in Summer 2026; its prompt rules were adapted, and the local model route is our own different path.

Score = 100 x (ln p(outcome) - ln community p(outcome)), the usual stand-in for the peer score. Replays used the original research and stated date, so outcomes cannot leak.

| Test | n | Result | Effective? |
|---|---|---|---|
| Old bot (flash-lite, template prompts) | 20 resolved binary | -19.7, Brier 0.214 (community 0.134) | baseline |
| New prompts, Claude Opus 5.5 | 20 | -8.2, Brier 0.174 | yes, weak (P>0 0.85) |
| New prompts, Claude Sonnet 5.5 | 20 | -10.3, Brier 0.181 | yes, weak (0.77) |
| New prompts, DeepSeek flash | 19 | -10.5, Brier 0.180 | yes, weak (0.87) |
| New prompts, gpt-6.1-sol | 20 | +1.5, Brier 0.124 | yes (+21.3 vs old, 95% interval +4.5 to +42.3) |
| Equal-weight median of four models | 20 | -7.9, Brier 0.172 | no, weaker models pull sol down |
| Three sol, Opus, Sonnet (median of five) | 20 | +2.2, Brier 0.122 | chosen; n is small, so the mix is only a mild preference |
| Full pipeline on closed unresolved binary (live search) | 8 | mean gap to community 0.088, old 0.170 | yes, proxy only: no outcomes yet |

## Known issues
- gemini-3.6-flash and gemini-3.5-flash have small free daily quotas (about 20 to 30 requests), so the hosted runner reaches flash-lite after a question or two.
- The DeepSeek route through the local gateway sometimes returns 502, and the Codex researcher fails occasionally. The pipeline tolerates both.
- The old checkout in Documents/Codex/2026-09-23/ is stale; work here.
