# Fine Print：DEV × Kaggle Benchmarking Challenge 参赛材料

- 挑战页：https://dev.to/challenges/kaggle-2026-09-23
- 截止时间：**2026-10-11 23:59 PDT**（北京时间 10-12 14:59）
- 评分标准：洞见、写作质量、创意。文章里必须放 Kaggle benchmark 的链接。

| 文件 | 用途 |
|---|---|
| `fine_print_bench.py` | Kaggle notebook 代码，包含题库：40 组最小对照题，共 80 题，8 类陷阱 |
| `fine_print_bench.ipynb` | 由上面的 `.py` 生成，可直接导入 Kaggle |
| `make_notebook.py` | 把 `.py` 转成 `.ipynb` 的脚本 |
| `DEV_POST_DRAFT.md` | DEV 参赛文章草稿（英文），`[[...]]` 处要换成真实跑出来的数字 |

## 在浏览器里的步骤

### 1. Kaggle：建任务（约 10 分钟）
1. 登录 kaggle.com。如果账号还没做手机验证，先去 Settings 里验证，不验证可能用不了模型。
2. 打开 https://www.kaggle.com/benchmarks/tasks/new ，会自动新建一个预装好 `kaggle-benchmarks` 的 notebook。
3. 菜单 **File → Import Notebook**，上传 `fine_print_bench.ipynb`。这个文件已经切好单元格，最后一格的 `%choose fine_print_forecasting` 也已经打开。
   - 如果导入不了：就把 `fine_print_bench.py` 按 `# %%` 分隔符逐段粘进单元格，最后一格写 `%choose fine_print_forecasting`，前面不要带 `#`。
4. 改了 `.py` 之后，运行 `python3 kaggle_benchmark/make_notebook.py` 重新生成 `.ipynb`。
5. 点 Run All，确认主任务打印出了 `pair_accuracy`。
6. 点 **Save Version**。

### 2. Kaggle：跑多个模型（约 15–30 分钟）
1. 打开刚生成的任务页面，点 **Evaluate More Models**，选 4–6 个模型。建议混搭：前沿推理模型、便宜快速模型、开源权重模型、小模型。
2. 跑完就有 leaderboard 了。把它建成或发布为 benchmark，然后复制 benchmark 的链接。
3. 文章还需要分类数据和消融实验数据：回到 notebook，把 `REPORT_MODELS` 填 2–3 个模型 id。可用的 id 在上一个单元格里打印出来了。然后运行分析单元格，把打印出的三张表复制下来。

### 3. DEV：发帖（约 30 分钟）
1. 登录 dev.to，在挑战页点 **Submit**。这样会带上官方模板和标签。
2. 把 `DEV_POST_DRAFT.md` 的内容粘进去，把所有 `[[...]]` 换成真实数字和链接。
3. 按自己的数据写 “What I learned”。草稿里那些只是提示你去找的方向，不是结论。
4. 预览，然后 Publish。务必在截止时间前发布。

## 本地自测

这里没有 Kaggle 的模型权限，所以用替身模块验证了评分逻辑：
- 完美模型：pair accuracy 100%
- 无视细则、两题答一样的模型：0%
- 输出解析失败的模型：0%

真实分数只能在 Kaggle 上跑出来。
