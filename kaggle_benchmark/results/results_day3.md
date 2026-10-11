_26 models. Isolated = each statement in a fresh chat; joint = whole family in one prompt. Arbitrage-free = a bookie trading at most $1 per contract can lock in at most 5¢. Batch-run rows are re-scored from the saved raw replies with the fraction-aware parser (see merge_runs.py)._

### Leaderboard
```
                                      score (arbitrage-free %, isolated)  mean arbitrage ¢/family (isolated)  control-only ¢/family  arbitrage-free % (joint)                       run
google/gemini-3.8-flash                                             89.2                                 2.0                    0.0                     100.0  Kaggle batch run, 11 Oct
openai/gpt-5.5-2026-04-23                                           83.8                                 2.3                    0.0                     100.0  Kaggle batch run, 11 Oct
google/gemini-3.7-flash                                             83.8                                 2.0                    0.0                     100.0  notebook session, 10 Oct
google/gemini-3.1-flash-lite-preview                                78.4                                 4.5                    0.0                     100.0  notebook session, 10 Oct
anthropic/claude-haiku-5-5                                          78.4                                 4.7                    0.0                     100.0  notebook session, 10 Oct
google/gemini-3.5-flash                                             78.4                                 3.9                    0.0                     100.0  Kaggle batch run, 11 Oct
google/gemini-3.6-flash                                             75.7                                 4.2                    0.0                     100.0  Kaggle batch run, 11 Oct
anthropic/claude-sonnet-5-5@default                                 75.7                                 3.6                    0.0                     100.0  Kaggle batch run, 11 Oct
anthropic/claude-opus-4-8@default                                   75.7                                 4.2                    0.0                     100.0  notebook session, 10 Oct
anthropic/claude-opus-4-6@default                                   75.7                                 3.9                    0.0                     100.0  notebook session, 10 Oct
anthropic/claude-opus-4-7@default                                   73.0                                 4.9                    0.0                      97.3  notebook session, 10 Oct
openai/gpt-5.6-luna                                                 73.0                                 4.5                    0.0                     100.0  Kaggle batch run, 11 Oct
google/gemini-3.5-flash-lite                                        69.4                                 6.1                    0.3                      97.3  notebook session, 10 Oct
google/gemma-4-31b                                                  69.4                                 5.7                    0.0                     100.0  Kaggle batch run, 11 Oct
anthropic/claude-sonnet-5@default                                   67.6                                 6.5                    0.0                     100.0  Kaggle batch run, 11 Oct
google/gemini-3-flash-preview                                       67.6                                 3.9                    0.0                     100.0  Kaggle batch run, 11 Oct
google/gemini-3.1-pro-preview                                       67.6                                 4.2                    0.0                      97.3  Kaggle batch run, 11 Oct
anthropic/claude-opus-4-5@20251101                                  67.6                                 5.4                    1.0                     100.0  notebook session, 10 Oct
qwen/qwen3-235b-a22b-instruct-2507                                  64.9                                 8.8                    0.6                     100.0  notebook session, 10 Oct
anthropic/claude-haiku-4-5@20251001                                 64.9                                 6.9                    0.0                      97.3  notebook session, 10 Oct
qwen/qwen3-next-80b-a3b-instruct                                    62.2                                14.6                    3.2                     100.0  Kaggle batch run, 11 Oct
openai/gpt-5.4-mini-2026-03-17                                      59.5                                 8.1                    0.0                     100.0  notebook session, 10 Oct
xai/grok-4.20-0309-non-reasoning                                    56.8                                 7.9                    7.3                     100.0  Kaggle batch run, 11 Oct
openai/gpt-5.4-nano-2026-03-17                                      55.6                                 7.5                    0.0                     100.0  notebook session, 10 Oct
qwen/qwen3-coder-480b-a35b-instruct                                 51.4                                11.4                    0.7                     100.0  Kaggle batch run, 11 Oct
openai/gpt-oss-20b                                                  48.6                                18.7                    0.0                      94.6  notebook session, 10 Oct
```

### Guaranteed arbitrage by family type (¢ per family, isolated)
```
ftype                                 conjunction  deadline  negation  partition  story  threshold
google/gemini-3.8-flash                       4.3       0.0       2.6        2.5    1.5        0.0
openai/gpt-5.5-2026-04-23                     3.4       0.0       5.3        2.7    0.0        0.0
google/gemini-3.7-flash                       4.0       0.0       2.8        3.6    0.0        0.0
google/gemini-3.1-flash-lite-preview          9.3       0.0       2.5       10.1    0.0        1.4
anthropic/claude-haiku-5-5                    9.4       0.0       8.2        6.0    0.0        0.0
google/gemini-3.5-flash                       4.6       0.0      10.0        4.9    0.0        0.0
google/gemini-3.6-flash                       8.0       0.3       6.9        6.1    0.0        0.0
anthropic/claude-sonnet-5-5@default           4.1       0.0       5.3        8.4    1.3        0.0
anthropic/claude-opus-4-8@default            10.9       0.0       5.5        4.3    1.3        0.0
anthropic/claude-opus-4-6@default             7.6       0.0       7.5        4.6    0.0        0.0
anthropic/claude-opus-4-7@default            15.3       0.0       5.1        4.7    0.0        0.0
openai/gpt-5.6-luna                           9.6       0.0       5.1        8.0    1.0        0.0
google/gemini-3.5-flash-lite                 11.0       1.3       8.4        9.7    0.8        1.4
google/gemma-4-31b                           15.9       0.0       7.9        4.1    0.0        1.4
anthropic/claude-sonnet-5@default            17.3       2.5       8.1        4.4    3.3        0.0
google/gemini-3-flash-preview                 7.6       0.0       6.9        4.3    1.8        0.0
google/gemini-3.1-pro-preview                10.4       0.0       5.4        5.7    0.0        0.0
anthropic/claude-opus-4-5@20251101           16.6       0.0       4.2        6.3    1.8        0.0
qwen/qwen3-235b-a22b-instruct-2507           29.3       0.0       2.7       12.0    0.0        2.4
anthropic/claude-haiku-4-5@20251001          12.3       1.0       8.0       13.6    1.3        0.3
qwen/qwen3-next-80b-a3b-instruct             37.4       2.5      19.4       15.2    1.3        0.3
openai/gpt-5.4-mini-2026-03-17               11.6       2.0      14.0       11.3    0.0        2.9
xai/grok-4.20-0309-non-reasoning             15.7       1.8      12.5       10.7    0.0        0.0
openai/gpt-5.4-nano-2026-03-17               14.1       5.3       9.9        9.5    0.2        1.0
qwen/qwen3-coder-480b-a35b-instruct          20.4       2.5       8.4       26.1    0.0        2.9
openai/gpt-oss-20b                           40.9       5.5      14.4       16.5    2.5       20.5
```

### Arbitrage-free rate by family type (isolated, all models)
```
ftype
conjunction    49.0
deadline       93.0
negation       57.0
partition      52.0
story          95.0
threshold      94.0
```
