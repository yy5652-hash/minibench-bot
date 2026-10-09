"""Convert fine_print_bench.py (# %% cells) into fine_print_bench.ipynb for Kaggle import."""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
src = (HERE / "fine_print_bench.py").read_text()

cells = []
for chunk in re.split(r"^# %%", src, flags=re.M)[1:]:
    header, _, body = chunk.partition("\n")
    if header.strip() == "[markdown]":
        text = "\n".join(re.sub(r"^# ?", "", line) for line in body.strip().splitlines())
        cells.append({"cell_type": "markdown", "metadata": {}, "source": text})
    else:
        # The %choose magic is commented out so the .py runs as plain Python; enable it here.
        body = body.replace("# %choose ", "%choose ")
        cells.append(
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": body.strip(),
            }
        )

nb = {
    "cells": cells,
    "metadata": {"language_info": {"name": "python"}},
    "nbformat": 4,
    "nbformat_minor": 5,
}
(HERE / "fine_print_bench.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
print(f"wrote {len(cells)} cells")
