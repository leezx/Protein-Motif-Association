"""Genome coverage vs ATAC-peak recall for the protein-hotspot ranking (and a pan-cellular ATAC ranking).

usage: 40_coverage_recall.py <peaks.narrowPeak> <bins500.npz> <bins_annotation.npz> <out_prefix> [tier=20000]

Universe = kept 500 bp bins (31_hotspot_annotation.py: no ENCODE blacklist overlap, N <= 50 %); peaks and bins are
both restricted to it. Peaks as in 37 (chr1-22, X, Y; sub-peaks collapsed; ATAC tiers by fold enrichment: high
1..T, mid T+1..2T, low 2T+1..3T, all). For a bin score s (P = distinct ChIP-Atlas proteins, or A = ChIP-Atlas ATAC
experiments open) and threshold t: coverage(t) = kept bins with s >= t / kept bins; recall(t) = peaks with
score >= t, where the peak score is the max s over its kept bins (overlap) or s of its summit bin (summit). Peaks
with no kept bin (overlap) or a dropped summit bin (summit) are removed from that basis. With the P ranking,
'overlap' recall at t = 17 / 36 / 70 / 244 equals the share of peaks overlapping the top20 / 10 / 5 / 1 hotspot BED.
Writes <out_prefix>.curve.tsv.gz (score, threshold, coverage, recall per tier and basis) and
<out_prefix>.at_hotspot_thresholds.tsv.
"""
import sys

import numpy as np
import pandas as pd

BIN = 500
THR = {"top1": 244, "top5": 70, "top10": 36, "top20": 17}


def main(peaks, npz, ann, out, T=20000):
    z, a = np.load(npz), np.load(ann)
    chroms = list(z["chrom"])
    offs = dict(zip(chroms, z["offset"].astype(np.int64)))
    nb = dict(zip(chroms, z["n_bins"].astype(np.int64)))
    keep = a["keep"]
    scores = {"protein_hotspot": z["proteins"].astype(np.int64), "chipatlas_atac": z["atac_experiments"].astype(np.int64)}
    d = pd.read_csv(peaks, sep="\t", header=None, usecols=[0, 1, 2, 6, 9], names=["chrom", "start", "end", "fe", "summit"])
    d = d[d.chrom.isin(offs)].sort_values("fe", ascending=False).drop_duplicates(["chrom", "start", "end"])
    r = np.arange(1, len(d) + 1)
    tier = np.select([r <= T, r <= 2 * T, r <= 3 * T], ["high", "mid", "low"], "rest")
    o = d.chrom.map(offs).to_numpy()
    n = d.chrom.map(nb).to_numpy()
    b0 = o + d.start.to_numpy() // BIN
    b1 = o + np.minimum((d.end.to_numpy() - 1) // BIN, n - 1)
    sb = o + np.minimum((d.start.to_numpy() + d.summit.to_numpy()) // BIN, n - 1)
    N = int(keep.sum())
    rows, at = [], []
    for sname, S in scores.items():
        pk_ov = np.full(len(d), -1, np.int64)
        for k in range(int((b1 - b0).max()) + 1):
            m = b0 + k <= b1
            idx = b0[m] + k
            v = np.where(keep[idx], S[idx], -1)
            pk_ov[m] = np.maximum(pk_ov[m], v)
        pk_su = np.where(keep[sb], S[sb], -1)
        sk = np.sort(S[keep])[::-1]
        thr = np.unique(sk)[::-1]
        thr = thr[thr > 0]
        cov = np.searchsorted(-sk, -thr, side="right") / N  # share of kept bins with s >= t
        out_cols = dict(score=sname, threshold=thr, coverage=cov)
        for basis, pk in (("overlap", pk_ov), ("summit", pk_su)):
            for tname in ("high", "mid", "low", "all"):
                m = (pk >= 0) & ((tier == tname) if tname != "all" else True)
                v = np.sort(pk[m])[::-1]
                rec = np.searchsorted(-v, -thr, side="right") / len(v)
                out_cols[f"recall_{tname}_{basis}"] = rec
                if sname == "protein_hotspot":
                    for hn, t in THR.items():
                        at.append(dict(hotspot=hn, threshold=t, basis=basis, atac_tier=tname, peaks=len(v),
                                       genome_coverage=float((S[keep] >= t).mean()),
                                       genome_Mb=float((S[keep] >= t).sum() * BIN / 1e6),
                                       recall=float((v >= t).mean())))
        rows.append(pd.DataFrame(out_cols))
    curve = pd.concat(rows)
    curve.to_csv(f"{out}.curve.tsv.gz", sep="\t", index=False)
    at = pd.DataFrame(at)
    at["fold_over_random"] = at.recall / at.genome_coverage
    # matched comparison: coverage the ChIP-Atlas ATAC ranking needs to reach the same recall
    ca = curve[curve.score == "chipatlas_atac"]
    need = []
    for _, x in at.iterrows():
        col = f"recall_{x.atac_tier}_{x.basis}"
        ok = ca[ca[col] >= x.recall]
        need.append(float(ok.coverage.min()) if len(ok) else float("nan"))
    at["chipatlas_atac_coverage_same_recall"] = need
    at.to_csv(f"{out}.at_hotspot_thresholds.tsv", sep="\t", index=False)
    print(f"universe: {N} bins = {N * BIN / 1e9:.3f} Gb")
    print(at.round(4).to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:5], *(int(x) for x in sys.argv[5:6]))
