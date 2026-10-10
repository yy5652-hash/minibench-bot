_Run date: 2026-10-10. Isolated = each statement in a fresh chat; joint = whole family in one prompt. Arbitrage-free = a bookie trading at most $1 per contract can lock in at most 5¢._

### Leaderboard
```
                                      score (arbitrage-free %, isolated)  mean arbitrage ¢/family (isolated)  uncertain-only ¢/family  control-only ¢/family  control Brier  arbitrage-free % (joint)  mean arbitrage ¢/family (joint) parse failures (iso/joint)
model                                                                                                                                                                                                                                                            
google/gemini-3.7-flash                                           83.784                               2.043                    2.696                  0.011          0.000                   100.000                            0.000                        0/0
google/gemini-3.1-flash-lite-preview                              78.378                               4.488                    5.929                  0.005          0.000                   100.000                            0.000                        0/0
anthropic/claude-haiku-5-5                                        78.378                               4.703                    6.214                  0.000          0.000                   100.000                            0.054                        0/0
anthropic/claude-opus-4-6@default                                 75.676                               3.920                    5.179                  0.006          0.000                   100.000                            0.000                        0/0
anthropic/claude-opus-4-8@default                                 75.676                               4.191                    5.536                  0.006          0.000                   100.000                            0.020                       0/11
anthropic/claude-opus-4-7@default                                 72.973                               4.894                    6.464                  0.007          0.000                    97.297                            0.271                        0/0
google/gemini-3.5-flash-lite                                      69.444                               6.078                    8.000                  0.311          0.000                    97.297                            0.149                        1/0
anthropic/claude-opus-4-5@20251101                                67.568                               5.435                    6.857                  1.012          0.000                   100.000                            0.005                        0/0
anthropic/claude-haiku-4-5@20251001                               64.865                               6.924                    9.143                  0.021          0.000                    97.297                            1.786                        0/0
qwen/qwen3-235b-a22b-instruct-2507                                64.865                               8.849                   11.500                  0.600          0.001                   100.000                            0.000                        0/0
openai/gpt-5.4-mini-2026-03-17                                    59.459                               8.108                   10.714                  0.001          0.000                   100.000                            0.000                        0/0
openai/gpt-5.4-nano-2026-03-17                                    55.556                               7.546                    9.700                  0.005          0.003                   100.000                            0.054                        1/0
openai/gpt-oss-20b                                                48.649                              18.705                   24.713                  0.014          0.002                    94.595                            0.459                        0/0
```

### Guaranteed arbitrage by family type (¢ per family, isolated)
```
ftype                                 conjunction  deadline  negation  partition  story  threshold
model                                                                                             
google/gemini-3.7-flash                       4.0       0.0       2.8        3.6    0.0        0.0
google/gemini-3.1-flash-lite-preview          9.3       0.0       2.5       10.1    0.0        1.4
anthropic/claude-haiku-5-5                    9.4       0.0       8.2        6.0    0.0        0.0
anthropic/claude-opus-4-6@default             7.6       0.0       7.5        4.6    0.0        0.0
anthropic/claude-opus-4-8@default            10.9       0.0       5.5        4.3    1.3        0.0
anthropic/claude-opus-4-7@default            15.3       0.0       5.1        4.7    0.0        0.0
google/gemini-3.5-flash-lite                 11.0       1.3       8.4        9.7    0.8        1.4
anthropic/claude-opus-4-5@20251101           16.6       0.0       4.2        6.3    1.8        0.0
anthropic/claude-haiku-4-5@20251001          12.3       1.0       8.0       13.6    1.3        0.3
qwen/qwen3-235b-a22b-instruct-2507           29.3       0.0       2.7       12.0    0.0        2.4
openai/gpt-5.4-mini-2026-03-17               11.6       2.0      14.0       11.3    0.0        2.9
openai/gpt-5.4-nano-2026-03-17               14.1       5.3       9.9        9.5    0.2        1.0
openai/gpt-oss-20b                           40.9       5.5      14.4       16.5    2.5       20.5
```

### The most Dutch-bookable answers
- **qwen/qwen3-235b-a22b-instruct-2507**, `con_quake` (conjunction): **120.0¢** risk-free
  - 0.18 ← An earthquake of magnitude 7.0 or greater (USGS) has its epicenter in California between now and 31 December 2035.
  - 0.35 ← An earthquake of magnitude 7.0 or greater (USGS) has its epicenter in Japan's Kanto region between now and 31 December 2035.
  - 0.75 ← Between now and 31 December 2035, there is both an M7.0+ earthquake (USGS) with its epicenter in California and an M7.0+ earthquake with its epicenter in Japan's Kanto region.
  - 0.98 ← Between now and 31 December 2035, there is an M7.0+ earthquake (USGS) with its epicenter in California, or one in Japan's Kanto region, or both.
- **openai/gpt-oss-20b**, `con_quake` (conjunction): **108.0¢** risk-free
  - 0.99 ← An earthquake of magnitude 7.0 or greater (USGS) has its epicenter in California between now and 31 December 2035.
  - 0.01 ← An earthquake of magnitude 7.0 or greater (USGS) has its epicenter in Japan's Kanto region between now and 31 December 2035.
  - 1.00 ← Between now and 31 December 2035, there is both an M7.0+ earthquake (USGS) with its epicenter in California and an M7.0+ earthquake with its epicenter in Japan's Kanto region.
  - 0.90 ← Between now and 31 December 2035, there is an M7.0+ earthquake (USGS) with its epicenter in California, or one in Japan's Kanto region, or both.
- **openai/gpt-oss-20b**, `con_climate` (conjunction): **87.0¢** risk-free
  - 0.08 ← NASA GISTEMP reports a global mean surface temperature anomaly for calendar year 2028 above 1.30°C (relative to 1951-1980).
  - 0.15 ← The September 2028 Arctic sea ice minimum extent reported by NSIDC is below 4.0 million km².
  - 0.45 ← Both: NASA GISTEMP's 2028 global anomaly is above 1.30°C (relative to 1951-1980), and NSIDC's September 2028 Arctic sea ice minimum is below 4.0 million km².
  - 0.65 ← At least one: NASA GISTEMP's 2028 global anomaly is above 1.30°C (relative to 1951-1980), or NSIDC's September 2028 Arctic sea ice minimum is below 4.0 million km².
- **openai/gpt-oss-20b**, `thr_sea_ice` (threshold): **77.0¢** risk-free
  - 0.92 ← The September 2030 Arctic sea ice minimum extent reported by NSIDC is below 3.0 million km².
  - 0.15 ← The September 2030 Arctic sea ice minimum extent reported by NSIDC is below 3.5 million km².
  - 0.30 ← The September 2030 Arctic sea ice minimum extent reported by NSIDC is below 4.0 million km².
  - 0.60 ← The September 2030 Arctic sea ice minimum extent reported by NSIDC is below 4.5 million km².
- **openai/gpt-oss-20b**, `par_worldcup2030` (partition): **63.5¢** risk-free
  - 0.04 ← Spain wins the 2030 FIFA World Cup.
  - 0.05 ← France wins the 2030 FIFA World Cup.
  - 0.07 ← Brazil wins the 2030 FIFA World Cup.
  - 0.07 ← Argentina wins the 2030 FIFA World Cup.
  - 0.01 ← England wins the 2030 FIFA World Cup.
  - 0.12 ← A team other than Spain, France, Brazil, Argentina and England wins the 2030 FIFA World Cup.
- **google/gemini-3.1-flash-lite-preview**, `con_ipos` (conjunction): **60.0¢** risk-free
  - 0.65 ← OpenAI's shares (or the shares of a holding company that owns it) are publicly listed on a stock exchange before 1 January 2029.
  - 0.15 ← SpaceX's shares are publicly listed on a stock exchange before 1 January 2029.
  - 0.05 ← Both OpenAI (directly or via a holding company) and SpaceX have publicly listed shares on a stock exchange before 1 January 2029.
  - 0.15 ← At least one of OpenAI (directly or via a holding company) and SpaceX has publicly listed shares on a stock exchange before 1 January 2029.
- **qwen/qwen3-235b-a22b-instruct-2507**, `con_moon_race` (conjunction): **50.0¢** risk-free
  - 0.35 ← NASA lands astronauts on the Moon before 1 January 2031.
  - 0.65 ← China lands astronauts (taikonauts) on the Moon before 1 January 2031.
  - 0.65 ← Both NASA and China land astronauts on the Moon before 1 January 2031.
  - 0.85 ← NASA or China (or both) land astronauts on the Moon before 1 January 2031.
- **openai/gpt-5.4-mini-2026-03-17**, `neg_moon` (negation): **48.0¢** risk-free
  - 0.74 ← At least one human walks on the surface of the Moon before 1 January 2029.
  - 0.74 ← No human walks on the surface of the Moon between now and 1 January 2029.

Kept: dutch_book_bench.task.json
Kept: dutch_book_bench-run_id_Run_1_google_gemini-3.7-flash.run.json
