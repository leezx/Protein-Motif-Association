"""How many strong ATAC-seq peaks of one sample fall outside the protein hotspots, by ATAC tier and hotspot tier.

usage: 37_atac_vs_hotspot.py <peaks.narrowPeak> <bins500.npz> <bins_annotation.npz> <out_prefix> [tier=20000]

Peaks: chr1-22, X, Y; MACS sub-peaks sharing one interval are collapsed (max signalValue, summit of that row).
Ranked by signalValue (fold enrichment; -log10 q as a sensitivity ranking). ATAC tiers: high = ranks 1..T,
mid = T+1..2T, low = 2T+1..3T, rest. Hotspot class of a peak = max P (distinct ChIP-Atlas proteins, 23_hotspot_bins.py)
over the 500 bp bins it overlaps: top1 >= 244, top5 70-243, top10 36-69, top20 17-35, sub-hotspot 1-16, none 0;
'summit' uses only the bin holding the summit. Peaks touching an ENCODE blacklist bin are counted separately.
Per peak, at the summit bin: ENCODE cCRE class, TSS distance (31_hotspot_annotation.py) and the share of the 18,651
ChIP-Atlas ATAC experiments open there. Writes <out_prefix>.tsv (counts and shares), <out_prefix>.peaks.tsv.gz
(per peak) and <out_prefix>.strong_outside_top20.bed (high + mid peaks below the top20 hotspot threshold, no
blacklist; columns chrom, start, end, signalValue, P_max, cCRE, TSS distance).
"""
import sys

import numpy as np
import pandas as pd

BIN = 500
CCRE = ["PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none"]
CLASSES = ["top1", "top5", "top10", "top20", "sub-hotspot", "none"]


def hot_class(p):
    return np.select([p >= 244, p >= 70, p >= 36, p >= 17, p >= 1], CLASSES[:5], "none")


def main(peaks, npz, ann, out, T=20000):
    z, a = np.load(npz), np.load(ann)
    offs = dict(zip(list(z["chrom"]), z["offset"].astype(np.int64)))
    nb = dict(zip(list(z["chrom"]), z["n_bins"].astype(np.int64)))
    P, blk = z["proteins"].astype(np.int32), a["blacklist"]
    d = pd.read_csv(peaks, sep="\t", header=None, usecols=[0, 1, 2, 6, 8, 9], names=["chrom", "start", "end", "fe",
                                                                                      "q", "summit"])
    d = d[d.chrom.isin(offs)]
    d = d.sort_values("fe", ascending=False).drop_duplicates(["chrom", "start", "end"]).reset_index(drop=True)
    o = d.chrom.map(offs).to_numpy()
    n = d.chrom.map(nb).to_numpy()
    b0 = o + d.start.to_numpy() // BIN
    b1 = o + np.minimum((d.end.to_numpy() - 1) // BIN, n - 1)
    pmax = np.zeros(len(d), np.int32)
    bl = np.zeros(len(d), bool)
    for k in range(int((b1 - b0).max()) + 1):
        m = b0 + k <= b1
        idx = b0[m] + k
        pmax[m] = np.maximum(pmax[m], P[idx])
        bl[m] |= blk[idx]
    sb = o + np.minimum((d.start.to_numpy() + d.summit.to_numpy()) // BIN, n - 1)
    d["P_max"], d["P_summit"], d["blacklist"] = pmax, P[sb], bl
    d["hot"], d["hot_summit"] = hot_class(pmax), hot_class(P[sb])
    d["ccre"] = np.array(CCRE)[a["ccre"][sb]]
    d["tss_dist"] = a["tss_dist"][sb]
    d["chipatlas_atac_frac"] = z["atac_experiments"][sb] / 18651.0
    rows = []
    for rank_by in ("fe", "q"):
        r = d[rank_by].rank(ascending=False, method="first").to_numpy()
        tier = np.select([r <= T, r <= 2 * T, r <= 3 * T], ["high", "mid", "low"], "rest")
        for t in ("high", "mid", "low", "rest"):
            for basis in ("hot", "hot_summit"):
                m = (tier == t) & ~d.blacklist.to_numpy()
                s = d.loc[m, basis].value_counts()
                row = dict(rank_by=rank_by, atac_tier=t, basis="peak" if basis == "hot" else "summit",
                           peaks=int(m.sum()), blacklist_excluded=int(((tier == t) & d.blacklist.to_numpy()).sum()),
                           fe_min=float(d.loc[tier == t, "fe"].min()), fe_median=float(d.loc[tier == t, "fe"].median()))
                for c in CLASSES:
                    row[c] = int(s.get(c, 0))
                row["not_in_top20"] = row["sub-hotspot"] + row["none"]
                row["pct_not_in_top20"] = row["not_in_top20"] / max(row["peaks"], 1)
                row["pct_not_in_top5"] = (row["not_in_top20"] + row["top10"] + row["top20"]) / max(row["peaks"], 1)
                rows.append(row)
        if rank_by == "fe":
            d["atac_tier"] = tier
    pd.DataFrame(rows).to_csv(f"{out}.tsv", sep="\t", index=False)
    d.to_csv(f"{out}.peaks.tsv.gz", sep="\t", index=False)
    so = d[d.atac_tier.isin(["high", "mid"]) & d.hot.isin(["sub-hotspot", "none"]) & ~d.blacklist]
    so.sort_values(["chrom", "start"])[["chrom", "start", "end", "fe", "P_max", "ccre", "tss_dist"]].to_csv(
        f"{out}.strong_outside_top20.bed", sep="\t", index=False, header=False)
    print(f"unique peaks (chr1-22,X,Y): {len(d)}")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:5], *(int(x) for x in sys.argv[5:6]))
