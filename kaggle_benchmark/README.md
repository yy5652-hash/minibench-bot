# Dutch Book Bench: DEV × Kaggle Benchmarking Challenge entry

A Kaggle Community Benchmark that measures whether LLM forecasters are **coherent**: can a bookie with no
information lock in a risk-free profit against a model's probabilities? See the notebook's opening cell for the
method.

| File | Purpose |
|---|---|
| `dutch_book_bench.ipynb` | **Upload this to Kaggle.** Generated from the `.py`. |
| `dutch_book_bench.py` | Notebook source (py:percent). Edit this one. |
| `build_notebook.py` | `.py` → `.ipynb` |
| `test_offline.py` | Runs the full pipeline offline against mock LLMs |
| `DEV_POST.md` | Draft of the DEV post, with `[[...]]` placeholders to fill from the results |

```sh
pip install kaggle-benchmarks==0.6.1 matplotlib nbformat
python kaggle_benchmark/test_offline.py      # end-to-end test with mock models
python kaggle_benchmark/build_notebook.py    # regenerate the .ipynb after editing the .py
```

## 提交步骤（截止：PDT 10 月 11 日 23:59 = 北京时间 10 月 12 日 14:59）

本次挑战没有单独的报名表：在 DEV 上发布一篇带挑战标签、并附上 Kaggle benchmark 链接的文章，就算有效参赛。

1. **Kaggle 账号**：登录 kaggle.com。账号需要通过手机验证才能调用模型。
2. **创建任务笔记本**：打开 <https://www.kaggle.com/benchmarks/tasks/new>，它会生成一个预装了 `kaggle-benchmarks` 的笔记本。
   用 *File → Import Notebook* 上传 `dutch_book_bench.ipynb`（或把各个 cell 依次粘贴进去）。
3. **交互式 Run All**：会先跑默认模型，再在第 6 节逐个跑 `kbench.llms` 里的所有模型，每个模型约 160 次调用。
   如果额度不够，把 `ANALYSIS_MODELS` 改成 5 到 8 个有代表性的模型（不同厂商，含推理模型和非推理模型）。
   跑完后从 `/kaggle/working/` 下载 `results.md`、`dutch_book_bench.png` 和 `family_results.csv`。
4. **Save Version（Save & Run All）**：最后一个 cell 里的 `%choose dutch_book_bench` 会把这个任务登记到排行榜。
   批处理模式会自动跳过第 6 节，不会重复跑全部模型。
5. **扩充排行榜**：在任务页点 **Evaluate More Models**，把能选的模型全部选上，然后创建一个 Benchmark，把这个任务加进去并设为 Public。
   复制 Benchmark 链接（这是参赛的必需项）。
6. **写文章**：在 dev.to 打开挑战页 <https://dev.to/challenges/kaggle-2026-09-23> 并点击提交，或者直接新建文章。
   把 `DEV_POST.md` 粘贴进去，用 `results.md` 的内容替换所有 `[[...]]`，删掉数据不支持的论点，上传图表，然后发布。

拿高分的要点（评分维度：发现是否真有洞察、文章是否清晰好读、benchmark 是否原创）：
- 标题和 TL;DR 里要放一个**具体、反直觉的例子**（`results.md` 里 “most Dutch-bookable answers” 那一节的第一条）。
- 一定要写出 **isolated 和 joint 的差距**，以及 **controls 和真实问题的差距**：这两个对比是本文的核心发现。
- 模型覆盖面越广越好（获奖示例都是跑了 Kaggle 上能用的全部模型）。
