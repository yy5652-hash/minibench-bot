"""Build dutch_book_bench.ipynb from the py:percent source dutch_book_bench.py.

Usage: python kaggle_benchmark/build_notebook.py
"""

import re
from pathlib import Path

import nbformat

HERE = Path(__file__).parent
SRC = HERE / "dutch_book_bench.py"
DST = HERE / "dutch_book_bench.ipynb"


def build() -> nbformat.NotebookNode:
    source = SRC.read_text().replace("# ==== RUN ====\n", "")
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    for chunk in re.split(r"^# %%", source, flags=re.M)[1:]:
        header, _, body = chunk.partition("\n")
        body = body.strip("\n")
        if header.strip() == "[markdown]":
            text = "\n".join(re.sub(r"^# ?", "", line) for line in body.splitlines())
            nb.cells.append(nbformat.v4.new_markdown_cell(text))
        else:
            # `# CHOOSE: task` is a comment in the .py source (so it stays importable) and the %choose magic in the notebook.
            body = re.sub(r"^# CHOOSE: (\S+)$", r"%choose \1", body, flags=re.M)
            nb.cells.append(nbformat.v4.new_code_cell(body))
    return nb


if __name__ == "__main__":
    nbformat.write(build(), DST)
    print(f"wrote {DST}")
