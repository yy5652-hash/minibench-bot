"""Run the whole benchmark offline against mock LLMs (no Kaggle model proxy needed).

Usage: python kaggle_benchmark/test_offline.py
Requires: kaggle-benchmarks, scipy, pandas, matplotlib.
"""

import hashlib
import os
import random
import re
import tempfile
from pathlib import Path

SRC = Path(__file__).with_name("dutch_book_bench.py")


class MockLLM:
    """A forecaster with per-question noise. `noise=0` is perfectly coherent on the control families."""

    def __init__(self, name, noise, joint_noise, refuse=()):
        self.name, self.noise, self.joint_noise, self.refuse = name, noise, joint_noise, refuse

    def _base(self, text):
        # deterministic "belief" for a statement; complements of the same event share a seed
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return (h % 1000) / 1000

    def prompt(self, message, **_):
        rng = random.Random(f"{self.name}|{message}")
        if "For each statement below" in message:
            n = len(re.findall(r"^Q\d+\. ", message, flags=re.M))
            ps = [min(1, max(0, 1 / n + rng.gauss(0, self.joint_noise))) for _ in range(n)]
            return "Some reasoning.\n" + "\n".join(f"Q{i + 1}: {p:.2f}" for i, p in enumerate(ps))
        statement = re.search(r'"(.*)"', message, flags=re.S).group(1)
        if any(word in statement for word in self.refuse):
            return "I can't predict elections."
        p = min(1, max(0, self._base(statement) + rng.gauss(0, self.noise)))
        return f"Reasoning here.\n**Probability:** {100 * p:.0f}%"


def main():
    source = SRC.read_text()
    setup, run_part = source.split("# ==== RUN ====")
    run_part = run_part.split("main_run = dutch_book_bench.run(kbench.llm)\nmain_run")[1]
    run_part = run_part.replace("sorted(kbench.llms)", "list(MOCKS)").replace("kbench.llms[model_name]", "MOCKS[model_name]")

    os.chdir(tempfile.mkdtemp())
    ns = {"__name__": "__dbb__", "display": print}
    exec(compile(setup, str(SRC), "exec"), ns)
    ns["MOCKS"] = {
        m.name: m
        for m in (
            MockLLM("mock/sloppy", noise=0.25, joint_noise=0.05),
            MockLLM("mock/careful", noise=0.02, joint_noise=0.01),
            MockLLM("mock/refuser", noise=0.1, joint_noise=0.05, refuse=("presidential",)),
        )
    }
    run = ns["dutch_book_bench"].run(ns["MOCKS"]["mock/sloppy"])
    print("main task result:", run.result)
    assert isinstance(run.result, float) and 0 <= run.result <= 100
    exec(compile(run_part, str(SRC), "exec"), ns)

    results = ns["RESULTS"]
    assert set(results) == {"mock/sloppy", "mock/careful", "mock/refuser"}
    fam = results["mock/refuser"]["families"]
    assert not fam.loc[(fam.fid == "par_us2028") & (fam["mode"] == "isolated"), "parsed"].item()
    assert Path("results.md").exists() and Path("dutch_book_bench.png").exists()
    print("\nOFFLINE TEST PASSED in", os.getcwd())


if __name__ == "__main__":
    main()
