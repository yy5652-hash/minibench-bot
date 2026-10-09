"""Render the write-up chart from a results cache (dbb_results.json written by the notebook).

Usage: python kaggle_benchmark/make_chart.py kaggle_benchmark/results/dbb_results.json kaggle_benchmark/results/dutch_book_bench.png
"""

import json
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

matplotlib.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
BLUE, ORANGE = "#2a78d6", "#eb6834"  # categorical slots 1 and 2 of the reference palette
SEQ = LinearSegmentedColormap.from_list("blue_seq", ["#ffffff", "#cde2fb", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"])
TEXT, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e6e6e6"
TYPE_ORDER = ["conjunction", "partition", "negation", "story", "deadline", "threshold"]


def short(name: str) -> str:
    return name.split("/", 1)[-1].replace("@default", "").replace("@20251001", "").replace("@20251101", "")


def main(src: str, dst: str) -> None:
    payload = json.load(open(src))
    fam = pd.concat(
        [pd.DataFrame(r["families"]).assign(model=m) for m, r in payload["results"].items()], ignore_index=True
    )
    iso, jnt = fam[fam["mode"] == "isolated"], fam[fam["mode"] == "joint"]
    rate = lambda s: 100 * s[s.parsed].arbitrage_free.mean()  # noqa: E731
    score = iso.groupby("model").apply(rate).sort_values()
    joint = jnt.groupby("model").apply(rate).reindex(score.index)
    by_type = (iso.groupby(["model", "ftype"]).arbitrage.mean() * 100).unstack().reindex(score.index)[TYPE_ORDER]
    labels = [short(m) for m in score.index]
    n = len(score)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, max(4.2, 0.5 * n + 2.2)), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.patch.set_facecolor("white")

    # Left: dumbbell per model, isolated vs joint
    y = np.arange(n)
    for yi, (a, b) in enumerate(zip(score.values, joint.values)):
        ax1.plot([a, b], [yi, yi], color=GRID, lw=2, zorder=1)
    ax1.scatter(score.values, y, s=90, color=BLUE, zorder=3, label="asked one statement per chat (isolated)")
    ax1.scatter(joint.values, y, s=90, color=ORANGE, marker="D", zorder=3, label="whole family in one prompt (joint)")
    for yi, v in enumerate(score.values):
        ax1.text(v - 1.2, yi, f"{v:.0f}%", va="center", ha="right", color=TEXT, fontsize=9)
    ax1.set_yticks(y, labels)
    ax1.set_xlim(40, 104)
    ax1.set_ylim(-0.7, n - 0.3 + 1.4)  # headroom for the legend
    ax1.set_xlabel("% of question families a bookie cannot Dutch-book for more than 5¢ (higher is better)", color=MUTED)
    ax1.set_title("Coherence collapses when questions are asked separately", loc="left", fontsize=12, color=TEXT)
    ax1.legend(loc="upper left", frameon=False, fontsize=9)
    ax1.grid(axis="x", color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)
    ax1.spines["left"].set_color(GRID)
    ax1.spines["bottom"].set_color(GRID)
    ax1.tick_params(colors=TEXT)

    # Right: heatmap of mean guaranteed arbitrage by family type
    vals = by_type.values[::-1]  # best model at the top, like the left panel
    im = ax2.imshow(vals, aspect="auto", cmap=SEQ, vmin=0, vmax=max(10, np.nanmax(vals)))
    ax2.set_xticks(range(len(TYPE_ORDER)), TYPE_ORDER, rotation=30, ha="right", color=TEXT)
    ax2.set_yticks(range(n), labels[::-1], color=TEXT)
    for (i, j), v in np.ndenumerate(vals):
        if not np.isnan(v):
            ax2.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=9, color="white" if v > 0.55 * im.norm.vmax else TEXT)
    ax2.set_title("Where the money is: guaranteed profit (¢ per family), isolated", loc="left", fontsize=12, color=TEXT)
    for s in ax2.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax2, shrink=0.75, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=MUTED)

    fig.suptitle("Dutch Book Bench: can a bookie with no information beat an LLM forecaster?", x=0.01, ha="left",
                 fontsize=14, color=TEXT, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(dst, dpi=170)
    print("wrote", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
