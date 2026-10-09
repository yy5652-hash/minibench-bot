# Checklist and timeline (all times UTC)

## Before kickoff: Mon 12 Oct 2026, 15:00 (registration closes then)

- [ ] Register on the lablab.ai event page with **Sign up with AMD** (AMD AI Developer Program
      account; approval can take time, so do it first).
- [ ] Claim the AMD Developer Cloud credits from the event page or welcome email, and check they
      appear on the AMD Cloud billing page.
- [ ] Create or join the team on lablab.ai (up to 6 people) and pick the track: **Reinvent Commerce**.
- [ ] Join the event Discord and read the official rules page, especially any rule on code written
      before the kickoff, the required demo format and the final prize per track.

## Build week: 12–18 Oct

- [ ] Start a 1× MI300X droplet. Run `deploy/serve_vllm.sh`, then `SMOKE=1 deploy/run_all.sh`, then
      the full `deploy/run_all.sh`. Expect about an hour of GPU time for the full run.
- [ ] Billing: a powered-off GPU droplet is still billed. Copy `results/` off the droplet, then
      **destroy** it. The credit covers MI300X time only (not volumes, snapshots or backups), expires
      30 days after it is deposited, and a card on file is charged once it runs out.
- [ ] Commit `results/` (backtests, benchmark, gpu_info, llm_cache.sqlite). `data/synthetic-store.json`
      is already committed; do not regenerate it, the cache is keyed on it.
- [ ] Put the real numbers into `README.md` (Results), `submission/lablab_form.md`,
      `video_script.md` and the slides. Report what the backtest says, including any weak spot.
- [ ] Record the video with the dashboard live on the MI300X.
- [ ] Deploy the `Dockerfile` (replay mode) to a free CPU host so the demo URL works during judging.
- [ ] Make the GitHub repository public, or publish `shelfcast/` as its own public repository.

## Submit before Sun 18 Oct 2026, 10:00 UTC (3:00 AM PDT, per the event schedule)

- [ ] The track brief says: "explain how the prediction was calculated. Do not use a language model as the
      only forecasting method." Say in the video and slides that the forecast is a statistical baseline plus
      a classical uplift model, with the LLM as the judgment layer and calibration on top.
- [ ] Submissions must be original and MIT-compliant (LICENSE is in this folder).
- [ ] Title, short and long description, track, technology tags, cover image
- [ ] Video and slide presentation
- [ ] Public GitHub repository
- [ ] Demo application URL
- [ ] On-site phase in Italy (17–18 Oct) is optional and by approval; travel is not covered.
