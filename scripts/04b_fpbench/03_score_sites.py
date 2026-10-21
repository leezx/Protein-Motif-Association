#!/usr/bin/env python3
"""Score every labelled motif site with every caller and compute per-TF AUPR / AUROC.

Site score = max caller score over [site start - PAD, site end + PAD).
  tobias       TOBIAS FootprintScores bigWig
  print_r10/20 PRINT -log10 p per bp (non-finite bp ignored; a site with no finite bp gets the minimum)
  hint         max HINT footprint BED score overlapping the site, 0 if none (thresholded caller)
  access       Tn5 insertions within +-100 bp of the site centre (accessibility only, no footprint model)
  naive_fp     -(FOS) from raw insertions: (C+1)/(L+1) + (C+1)/(R+1), C = site span, L/R = equal-width flanks
A TF is evaluated if it has >= MIN_SITES bound and >= MIN_SITES unbound sites.

usage: 03_score_sites.py <result_root>
output: <result_root>/eval/site_scores.tsv.gz, per_tf_metrics.tsv, summary.tsv
"""
import gzip, json, os, sys

import numpy as np
import pandas as pd
import pyBigWig
from sklearn.metrics import average_precision_score, roc_auc_score

PAD = 5
MIN_SITES = 30


def insertion_arrays(frags, sizes):
    ins = {c: np.zeros(sizes[c] + 1, dtype=np.int32) for c in sizes}
    for chunk in pd.read_csv(frags, sep="\t", header=None, usecols=[0, 1, 2], chunksize=5_000_000,
                             names=["c", "s", "e"], dtype={"c": str, "s": np.int64, "e": np.int64}):
        for c, g in chunk.groupby("c"):
            if c in ins:
                np.add.at(ins[c], g["s"].values, 1)
                np.add.at(ins[c], g["e"].values - 1, 1)
    return {c: np.concatenate([[0], np.cumsum(v, dtype=np.int64)]) for c, v in ins.items()}


def window_sum(cs, c, s, e):
    a = cs[c]
    s = np.clip(s, 0, len(a) - 1); e = np.clip(e, 0, len(a) - 1)
    return a[e] - a[s]


def bedgraph_arrays(path, sizes):
    arr = {c: np.full(sizes[c], np.nan, dtype=np.float32) for c in sizes}
    for chunk in pd.read_csv(path, sep="\t", header=None, names=["c", "s", "e", "v"], chunksize=5_000_000,
                             dtype={"c": str, "s": np.int64, "e": np.int64, "v": np.float64}):
        for c, g in chunk.groupby("c"):
            arr[c][g["s"].values] = g["v"].values
    return arr


def max_over(arr, sites):
    out = np.full(len(sites), np.nan)
    for i, (c, s, e) in enumerate(zip(sites.chrom.values, sites.start.values - PAD, sites.end.values + PAD)):
        v = arr[c][max(s, 0):e]
        v = v[np.isfinite(v)]
        if v.size:
            out[i] = v.max()
    return out


def main():
    R = sys.argv[1]
    os.makedirs(f"{R}/eval", exist_ok=True)
    sites = pd.read_csv(f"{R}/truth/sites.tsv.gz", sep="\t")
    chroms = sorted(sites.chrom.unique())
    sizes = {}
    for line in open("/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-17/reference/hg38.fa.fai"):
        c, n = line.split()[:2]
        if c in chroms:
            sizes[c] = int(n)
    scores = {}
    coverage = {}

    cs = insertion_arrays(f"{R}/inputs/atac.frags.tsv.gz", sizes)
    centre = (sites.start.values + sites.end.values) // 2
    scores["access"] = np.array([window_sum(cs, c, m - 100, m + 100) for c, m in zip(sites.chrom.values, centre)], float)
    w = sites.end.values - sites.start.values
    C = np.array([window_sum(cs, c, s, e) for c, s, e in zip(sites.chrom.values, sites.start.values, sites.end.values)])
    L = np.array([window_sum(cs, c, s - k, s) for c, s, k in zip(sites.chrom.values, sites.start.values, w)])
    Rr = np.array([window_sum(cs, c, e, e + k) for c, e, k in zip(sites.chrom.values, sites.end.values, w)])
    scores["naive_fp"] = -((C + 1) / (L + 1) + (C + 1) / (Rr + 1))

    bw_path = f"{R}/callers/tobias/tobias_footprints.bw"
    if os.path.exists(bw_path):
        bw = pyBigWig.open(bw_path)
        arr = {c: bw.values(c, 0, sizes[c], numpy=True).astype(np.float32) for c in chroms}
        scores["tobias"] = max_over(arr, sites)
        del arr

    bedgraphs = {f"print_r{r}": f"{R}/callers/print/print_r{r}.bedgraph.gz" for r in (10, 20)}
    bedgraphs.update({f"scprinter_r{r}": f"{R}/callers/scprinter/scprinter_r{r}.bedgraph.gz" for r in (10, 20)})
    bedgraphs["tracebind"] = f"{R}/callers/tracebind/tracebind_tf.bedgraph.gz"
    for name, p in bedgraphs.items():
        if os.path.exists(p):
            arr = bedgraph_arrays(p, sizes)
            scores[name] = max_over(arr, sites)
            del arr

    p = f"{R}/callers/hint/hint_footprints.bed"
    if os.path.exists(p):
        arr = {c: np.zeros(sizes[c], dtype=np.float32) for c in chroms}
        for line in open(p):
            f = line.split("\t")
            if f[0] in arr:
                s, e, v = int(f[1]), int(f[2]), float(f[4])
                seg = arr[f[0]][s:e]
                np.maximum(seg, v, out=seg)
        scores["hint"] = max_over(arr, sites)
        del arr

    for k, v in scores.items():
        coverage[k] = float(np.isfinite(v).mean())
        lo = np.nanmin(v) if np.isfinite(v).any() else 0.0
        scores[k] = np.where(np.isfinite(v), v, lo)  # no finite score inside the site -> weakest score
    out = sites.copy()
    for k, v in scores.items():
        out[k] = v
    out.to_csv(f"{R}/eval/site_scores.tsv.gz", sep="\t", index=False, compression="gzip")

    rows = []
    for tf, g in out.groupby("tf"):
        nb, nu = int(g.bound.sum()), int((g.bound == 0).sum())
        if nb < MIN_SITES or nu < MIN_SITES:
            continue
        # accessibility strata: quintiles of the access baseline within this TF's sites
        strata = pd.qcut(g.access.rank(method="first"), 5, labels=False)
        for k in scores:
            num = den = 0.0
            for _, h in g.groupby(strata):
                b, u = int(h.bound.sum()), int((h.bound == 0).sum())
                if b >= 10 and u >= 10:
                    wt = b * u  # stratified Mann-Whitney weight
                    num += wt * roc_auc_score(h.bound, h[k]); den += wt
            rows.append({"tf": tf, "method": k, "n_bound": nb, "n_unbound": nu,
                         "prevalence": nb / (nb + nu),
                         "aupr": average_precision_score(g.bound, g[k]),
                         "auroc": roc_auc_score(g.bound, g[k]),
                         "auroc_access_strat": num / den if den else np.nan})
    m = pd.DataFrame(rows)
    acc = m[m.method == "access"].set_index("tf")
    m["aupr_minus_access"] = m.aupr - m.tf.map(acc.aupr)
    m["auroc_minus_access"] = m.auroc - m.tf.map(acc.auroc)
    m["aupr_over_prevalence"] = m.aupr / m.prevalence
    m.to_csv(f"{R}/eval/per_tf_metrics.tsv", sep="\t", index=False)
    summ = m.groupby("method").agg(
        n_tf=("tf", "size"),
        median_aupr=("aupr", "median"),
        median_auroc=("auroc", "median"),
        median_aupr_over_prevalence=("aupr_over_prevalence", "median"),
        median_aupr_minus_access=("aupr_minus_access", "median"),
        median_auroc_minus_access=("auroc_minus_access", "median"),
        tf_beats_access_auroc=("auroc_minus_access", lambda x: int((x > 0).sum())),
        median_auroc_access_strat=("auroc_access_strat", "median"),
        n_tf_access_strat=("auroc_access_strat", lambda x: int(x.notna().sum())),
        tf_access_strat_ge_0_6=("auroc_access_strat", lambda x: int((x >= 0.6).sum())),
    ).reset_index()
    summ["site_coverage"] = summ.method.map(coverage)
    summ.sort_values("median_auroc", ascending=False).to_csv(f"{R}/eval/summary.tsv", sep="\t", index=False)
    print(summ.sort_values("median_auroc", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
