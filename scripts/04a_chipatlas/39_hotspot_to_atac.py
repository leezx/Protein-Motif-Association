"""Reverse of 37: what share of protein hotspots is accessible (has an ATAC peak) in one sample.

usage: 39_hotspot_to_atac.py <peaks.narrowPeak> <bins500.npz> <bins_annotation.npz> <hotspot_dir> <out_prefix>
                             [tier=20000]

Denominator = hotspots, not peaks. Peaks as in 37 (chr1-22, X, Y; sub-peaks collapsed; ATAC tier by fold
enrichment: high 1..T, mid T+1..2T, low 2T+1..3T, rest). A 500 bp bin (grid of 23_hotspot_bins.py; blacklist and
N > 50 % bins dropped) is open if any peak overlaps it by >= 1 bp; its ATAC class = strongest tier overlapping.
Bin sets: nested tiers top1 (P >= 244), top5 (>= 70), top10 (>= 36), top20 (>= 17); exclusive bands b1, b5
(70-243), b10 (36-69), b20 (17-35), sub (1-16), none (0) as baselines. Regions: PMA_hotspot_protein_<tier>.bed,
open if any peak overlaps. For top1 bins open vs not open in the sample: ChIP-Atlas ATAC open share (of 18,651
experiments) and open cell types (atac_celltypes), ENCODE cCRE class, TSS distance.
Writes <out_prefix>.bins.tsv, <out_prefix>.regions.tsv, <out_prefix>.top1_open_vs_closed.tsv,
<out_prefix>.top1_bins.tsv.gz (per top1 bin) and <out_prefix>.top1_closed.bed.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BIN = 500
CCRE = ["PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none"]
TIERS = {"top1": 244, "top5": 70, "top10": 36, "top20": 17}


def main(peaks, npz, ann, hot_dir, out, T=20000):
    z, a = np.load(npz), np.load(ann)
    chroms = list(z["chrom"])
    offs = dict(zip(chroms, z["offset"].astype(np.int64)))
    nb = dict(zip(chroms, z["n_bins"].astype(np.int64)))
    P = z["proteins"].astype(np.int32)
    keep = a["keep"]
    d = pd.read_csv(peaks, sep="\t", header=None, usecols=[0, 1, 2, 6], names=["chrom", "start", "end", "fe"])
    d = d[d.chrom.isin(offs)].sort_values("fe", ascending=False).drop_duplicates(["chrom", "start", "end"])
    r = np.arange(1, len(d) + 1)
    d["tier"] = np.select([r <= T, r <= 2 * T, r <= 3 * T], [1, 2, 3], 4)  # 1 = strongest
    best = np.full(len(P), 9, np.int8)  # 9 = no peak
    o = d.chrom.map(offs).to_numpy()
    n = d.chrom.map(nb).to_numpy()
    b0 = o + d.start.to_numpy() // BIN
    b1 = o + np.minimum((d.end.to_numpy() - 1) // BIN, n - 1)
    tv = d.tier.to_numpy().astype(np.int8)
    for k in range(int((b1 - b0).max()) + 1):
        m = b0 + k <= b1
        np.minimum.at(best, b0[m] + k, tv[m])
    open_ = best < 9
    names = {1: "high", 2: "mid", 3: "low", 4: "rest"}

    sets = {f"{t} (nested)": keep & (P >= v) for t, v in TIERS.items()}
    sets.update({"b5 (70-243)": keep & (P >= 70) & (P < 244), "b10 (36-69)": keep & (P >= 36) & (P < 70),
                 "b20 (17-35)": keep & (P >= 17) & (P < 36), "sub (1-16)": keep & (P >= 1) & (P < 17),
                 "none (0)": keep & (P == 0), "all bins": keep})
    rows = []
    for name, m in sets.items():
        x = best[m]
        row = dict(set=name, bins=int(m.sum()), pct_open=float((x < 9).mean()))
        for k, v in names.items():
            row[f"pct_{v}"] = float((x == k).mean())
        rows.append(row)
    pd.DataFrame(rows).to_csv(f"{out}.bins.tsv", sep="\t", index=False)

    reg_rows = []
    for t in TIERS:
        reg = pd.read_csv(Path(hot_dir) / f"PMA_hotspot_protein_{t}.bed", sep="\t", header=None, usecols=[0, 1, 2, 6])
        reg.columns = ["chrom", "start", "end", "n_bins"]
        rb0 = reg.chrom.map(offs).to_numpy() + reg.start.to_numpy() // BIN
        rn = ((reg.end - reg.start) // BIN).to_numpy()
        rb = np.full(len(reg), 9, np.int8)
        for k in range(int(rn.max())):
            m = k < rn
            rb[m] = np.minimum(rb[m], best[rb0[m] + k])
        row = dict(tier=t, regions=len(reg), pct_open=float((rb < 9).mean()),
                   pct_open_single_bin=float((rb[rn == 1] < 9).mean()))
        for k, v in names.items():
            row[f"pct_best_{v}"] = float((rb == k).mean())
        reg_rows.append(row)
    pd.DataFrame(reg_rows).to_csv(f"{out}.regions.tsv", sep="\t", index=False)

    t1 = np.flatnonzero(sets["top1 (nested)"])
    ci = np.searchsorted(z["offset"], t1, side="right") - 1
    df = pd.DataFrame(dict(chrom=np.array(chroms)[ci], start=(t1 - z["offset"][ci]) * BIN, P=P[t1],
                           open=open_[t1], atac_class=[names.get(int(v), "closed") for v in best[t1]],
                           chipatlas_atac_frac=z["atac_experiments"][t1] / 18651.0,
                           chipatlas_atac_celltypes=z["atac_celltypes"][t1],
                           chipatlas_dnase_frac=z["dnase_experiments"][t1] / 2086.0,
                           ccre=np.array(CCRE)[a["ccre"][t1]], tss_dist=a["tss_dist"][t1]))
    df.to_csv(f"{out}.top1_bins.tsv.gz", sep="\t", index=False)
    cmp = []
    for lab, m in (("open in sample", df.open), ("not open in sample", ~df.open)):
        x = df[m]
        row = dict(group=lab, bins=len(x), median_P=float(x.P.median()),
                   median_chipatlas_atac_frac=float(x.chipatlas_atac_frac.median()),
                   q25_chipatlas_atac_frac=float(x.chipatlas_atac_frac.quantile(.25)),
                   median_chipatlas_atac_celltypes=float(x.chipatlas_atac_celltypes.median()),
                   pct_atac_frac_ge10=float((x.chipatlas_atac_frac >= 0.10).mean()),
                   pct_atac_frac_lt1=float((x.chipatlas_atac_frac < 0.01).mean()),
                   median_dnase_frac=float(x.chipatlas_dnase_frac.median()),
                   pct_promoter_1kb=float((x.tss_dist <= 1000).mean()), pct_distal_5kb=float((x.tss_dist > 5000).mean()))
        for c in ("PLS", "pELS", "dELS", "CA-CTCF"):
            row[f"pct_{c}"] = float((x.ccre == c).mean())
        cmp.append(row)
    pd.DataFrame(cmp).to_csv(f"{out}.top1_open_vs_closed.tsv", sep="\t", index=False)
    df[~df.open].assign(end=lambda x: x.start + BIN)[["chrom", "start", "end", "P", "ccre", "chipatlas_atac_frac"]] \
        .to_csv(f"{out}.top1_closed.bed", sep="\t", index=False, header=False)
    for f in ("bins", "regions", "top1_open_vs_closed"):
        print(pd.read_csv(f"{out}.{f}.tsv", sep="\t").round(4).to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:6], *(int(x) for x in sys.argv[6:7]))
