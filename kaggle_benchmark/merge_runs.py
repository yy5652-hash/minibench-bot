"""Add batch-run outputs (`kaggle b t download dutch-book-bench -o DIR`) to the results cache.

Each run's raw replies are re-parsed and re-scored with the current parser in dutch_book_bench.py, so a parser
fix applies without re-spending quota. Models already in the cache from a notebook session keep that run.

Usage: python kaggle_benchmark/merge_runs.py kaggle_benchmark/results/dbb_results.json DIR/dutch-book-bench/3 [...]
"""

import glob
import json
import os
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).with_name("dutch_book_bench.py")


def load_benchmark() -> dict:
    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    ns = {"__name__": "__dbb__", "display": print}
    exec(compile(SRC.read_text().split("# ==== RUN ====")[0], str(SRC), "exec"), ns)
    os.chdir(cwd)
    return ns


def main(cache: str, *sources: str) -> None:
    ns = load_benchmark()
    payload = json.load(open(cache))
    for path in sorted(p for src in sources for p in glob.glob(f"{src}/*/*/dutch_book_bench-run_id*.run.json")):
        run = json.load(open(path))
        if "COMPLETED" not in run["state"] or "numericResult" not in run["results"][0]:
            continue
        model = run["modelVersion"]["slug"]
        prior = payload["results"].get(model)
        if prior and prior.get("source") != "batch":
            continue
        iso, joint = {}, {}
        for sub in run["subruns"]:
            d = (sub.get("results") or [{}])[0].get("dictResult") or {}
            if "qid" in d:
                iso[d["qid"]] = ns["parse_probability"](d["raw"])
            elif "fid" in d:
                n = len(ns["FAMILY_BY_ID"][d["fid"]]["questions"])
                for i, p in enumerate(ns["parse_joint"](d["raw"], n)):
                    joint[f"{d['fid']}.{i}"] = p
        fam_iso = ns["score_families"](iso).assign(mode="isolated")
        fam = [fam_iso, ns["score_families"](joint).assign(mode="joint")]
        families = json.loads(ns["pd"].concat(fam, ignore_index=True).to_json(orient="records"))
        score = float(100 * fam_iso[fam_iso["parsed"]]["arbitrage_free"].mean())
        payload["results"][model] = dict(model=model, score=score, api_errors=0, families=families, raw_isolated={},
                                         source="batch", kaggle_score=100 * run["results"][0]["numericResult"]["value"])
        print(f"{model}: {score:.1f} (Kaggle run reported {payload['results'][model]['kaggle_score']:.1f})")
    json.dump(payload, open(cache, "w"))


if __name__ == "__main__":
    main(*sys.argv[1:])
