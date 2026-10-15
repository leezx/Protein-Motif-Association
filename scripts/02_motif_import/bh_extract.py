"""Per-query BH over a full TOMTOM chunk, then keep only benchmark rows.

usage: bh_extract.py <tomtom.tsv> <n_targets> <benchmark_pairs.tsv> <out.tsv>

The BH family is every target of one query, self included (Step 1
convention, design §8.1). The universe is asserted complete before BH.
"""
import sys

import numpy as np
import pandas as pd


def bh(p):
    order = np.argsort(p, kind="mergesort")
    n = len(p)
    adj = p[order] * n / np.arange(1, n + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    q = np.empty_like(p)
    q[order] = np.minimum(adj, 1.0)
    return q


def main(path, n_targets, pairs_path, out):
    n_targets = int(n_targets)
    t = pd.read_csv(path, sep="\t", comment="#",
                    usecols=["Query_ID", "Target_ID", "Optimal_offset", "p-value", "Overlap", "Orientation"])
    size = t.groupby("Query_ID").size()
    assert (size == n_targets).all(), f"{path}: incomplete universe {size[size != n_targets].head()}"
    assert not t.duplicated(["Query_ID", "Target_ID"]).any(), f"{path}: duplicate pairs"
    assert t["p-value"].between(0, 1).all(), f"{path}: p out of range"
    p = t["p-value"].to_numpy(float)
    q = np.empty_like(p)
    for _, idx in t.groupby("Query_ID").indices.items():
        q[idx] = bh(p[idx])
    t["bh_q"] = q
    pr = pd.read_csv(pairs_path, sep="\t", usecols=["m1", "m2"])
    want = set(zip(pr.m1, pr.m2)) | set(zip(pr.m2, pr.m1))
    keep = [(a, b) in want for a, b in zip(t.Query_ID, t.Target_ID)]
    t[keep].to_csv(out, sep="\t", index=False)
    print(f"{path}: {size.size} queries x {n_targets} targets; kept {sum(keep)} rows")


if __name__ == "__main__":
    main(*sys.argv[1:])
