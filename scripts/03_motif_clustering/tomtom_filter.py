"""Per-query BH over one full TOMTOM chunk, keep rows with q < KEEP_Q.

usage: tomtom_filter.py <tomtom.tsv> <n_targets> <out.tsv.gz>

numpy only (runs on the system Python of the compute node). The BH family
is every target of one query, self included (Step 2 convention, design
§3.1). Completeness is asserted before BH: each query has exactly
n_targets rows, all targets distinct.
"""
import gzip
import sys

import numpy as np

KEEP_Q = 0.05
COLS = ["Query_ID", "Target_ID", "Optimal_offset", "p-value", "E-value", "q-value",
        "Overlap", "Query_consensus", "Target_consensus", "Orientation"]


def bh(p):
    order = np.argsort(p, kind="mergesort")
    n = len(p)
    adj = p[order] * n / np.arange(1, n + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    q = np.empty_like(p)
    q[order] = np.minimum(adj, 1.0)
    return q


def flush(qid, rows, n_targets, out):
    assert len(rows) == n_targets, f"{qid}: {len(rows)} rows != {n_targets}"
    assert len({r[1] for r in rows}) == n_targets, f"{qid}: duplicate targets"
    p = np.array([float(r[3]) for r in rows])
    assert ((p >= 0) & (p <= 1)).all(), f"{qid}: p out of range"
    q = bh(p)
    kept = 0
    for r, qq in zip(rows, q):
        if qq < KEEP_Q:
            out.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\t{qq:.6g}\t{r[6]}\t{r[9]}\n")
            kept += 1
    return kept


def main(path, n_targets, out_path):
    n_targets = int(n_targets)
    seen, kept, nq = set(), 0, 0
    with open(path) as fh, gzip.open(out_path, "wt") as out:
        assert fh.readline().rstrip("\n").split("\t") == COLS, "unexpected TOMTOM header"
        out.write("query\ttarget\toffset\tp\tq\toverlap\torientation\n")
        cur, rows = None, []
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            r = line.rstrip("\n").split("\t")
            if r[0] != cur:
                if cur is not None:
                    kept += flush(cur, rows, n_targets, out)
                    nq += 1
                assert r[0] not in seen, f"query {r[0]} not contiguous"
                seen.add(r[0])
                cur, rows = r[0], []
            rows.append(r)
        if cur is not None:
            kept += flush(cur, rows, n_targets, out)
            nq += 1
    print(f"{path}: {nq} queries x {n_targets} targets; kept {kept} rows (q<{KEEP_Q})")


if __name__ == "__main__":
    main(*sys.argv[1:])
