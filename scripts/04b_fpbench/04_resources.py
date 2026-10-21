#!/usr/bin/env python3
"""Collect caller resource records into one table, with a linear extrapolation to all K562 peak windows.

Extrapolation multiplies wall and CPU by full_windows / benchmark_windows. Fixed costs (bias loading, imports)
do not scale, so the extrapolated numbers are upper estimates. Peak memory is not extrapolated.

usage: 04_resources.py <result_root> <full_windows>
output: <result_root>/eval/resources.tsv
"""
import json, os, sys

import pandas as pd

TOOLS = ["tobias", "hint", "print", "print_cpu", "tracebind", "scprinter"]


def main():
    R, full = sys.argv[1], int(sys.argv[2])
    n = sum(1 for _ in open(f"{R}/inputs/regions_1kb.bed"))
    rows = []
    for t in TOOLS:
        p = f"{R}/callers/{t}/resource.json"
        if not os.path.exists(p):
            continue
        r = json.load(open(p))
        rows.append({
            "tool": t, "exit_code": r["exit_code"], "cores": 16, "windows": n,
            "wall_min": r["wall_s"] / 60,
            "cpu_h": r["cpu_total_s"] / 3600,
            "cpu_source": "sampled+rusage" if "cpu_sampled_s" in r else "rusage only (misses forked workers)",
            "avg_cores_busy": r["avg_cores_busy"],
            "peak_pss_gb": r["peak_pss_gb"],
            "windows_per_min": n / (r["wall_s"] / 60),
            "full_genome_wall_h_16c": r["wall_s"] * full / n / 3600,
            "full_genome_cpu_h": r["cpu_total_s"] * full / n / 3600,
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"{R}/eval/resources.tsv", sep="\t", index=False, float_format="%.3f")
    print(df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
