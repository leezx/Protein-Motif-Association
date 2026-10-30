"""HT29 dTAG-SOX9 time course: consensus ATAC regions, fragment counts and CUT&RUN occupancy calls (Context Query v0.1).

usage: 45_ht29_dtag_counts.py <manifest.tsv> <out_dir> [threads=8]

manifest.tsv columns: sample, assay (ATAC | SOX9 | SMARCC1 | IgG), time (DMSO, D2, D4, D7, D10, D13), rep, bam, peaks
(MACS narrowPeak; '.' when none). Chromosomes chr1-22, X.
Regions: per ATAC sample, unique peak intervals -> summit +-250 bp; windows of all 12 samples are merged and a merged
region is kept when >= 2 samples contribute (sample support written as n_samples). Regions do not overlap.
Counts: one per fragment = properly paired, MAPQ >= 10, leftmost mate (tlen > 0), assigned by fragment midpoint;
lib_size = all such fragments on chr1-22, X. Occupancy: region overlaps a narrowPeak of the sample (any overlap);
per (assay, time) both replicates -> <assay>_<time>_both, either -> _any.
Writes regions.bed, counts.tsv.gz (region x sample), lib_size.tsv, occupancy.tsv.gz, peaks_in_universe.tsv
(share of each CUT&RUN sample's peaks that touch a region; the universe is HT29 open chromatin only).
"""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
import pysam

CHROMS = [f"chr{i}" for i in range(1, 23)] + ["chrX"]
HALF = 250


def read_peaks(path):
    d = pd.read_csv(path, sep="\t", header=None, usecols=[0, 1, 2, 9], names=["chrom", "start", "end", "summit"])
    return d[d.chrom.isin(CHROMS)].drop_duplicates(["chrom", "start", "end"])


def consensus(atac):
    w = []
    for name, path in atac:
        d = read_peaks(path)
        c = d.start + d.summit
        w.append(pd.DataFrame(dict(chrom=d.chrom, start=np.maximum(c - HALF, 0), end=c + HALF, sample=name)))
    w = pd.concat(w).sort_values(["chrom", "start"]).reset_index(drop=True)
    out = []
    for chrom, g in w.groupby("chrom", sort=False):
        s, e, smp = g.start.to_numpy(), g.end.to_numpy(), g["sample"].to_numpy()
        run_end = np.maximum.accumulate(e)
        new = np.r_[True, s[1:] >= run_end[:-1]]
        gid = np.cumsum(new) - 1
        rs = pd.DataFrame(dict(gid=gid, s=s, e=e, smp=smp)).groupby("gid").agg(
            start=("s", "min"), end=("e", "max"), n_samples=("smp", "nunique"))
        rs["chrom"] = chrom
        out.append(rs)
    r = pd.concat(out)
    r = r[r.n_samples >= 2]
    r["chrom"] = pd.Categorical(r.chrom, CHROMS)
    r = r.sort_values(["chrom", "start"]).reset_index(drop=True)
    r["chrom"] = r.chrom.astype(str)
    r.insert(0, "region", [f"R{i:06d}" for i in range(len(r))])
    return r[["region", "chrom", "start", "end", "n_samples"]]


def count_bam(args):
    bam, regions = args
    counts = np.zeros(len(regions), np.int32)
    lib = 0
    with pysam.AlignmentFile(bam) as f:
        for chrom in CHROMS:
            idx = np.flatnonzero(regions.chrom.to_numpy() == chrom)
            st, en = regions.start.to_numpy()[idx], regions.end.to_numpy()[idx]
            mids = []
            for r in f.fetch(chrom):
                if (r.is_proper_pair and r.template_length > 0 and r.mapping_quality >= 10
                        and not r.is_secondary and not r.is_supplementary and not r.is_duplicate):
                    mids.append(r.reference_start + r.template_length // 2)
            mids = np.asarray(mids, np.int64)
            lib += len(mids)
            if len(idx) and len(mids):
                j = np.searchsorted(st, mids, side="right") - 1
                ok = (j >= 0) & (mids < en[np.maximum(j, 0)])
                np.add.at(counts, idx[j[ok]], 1)
    return counts, lib


def overlaps(regions, peaks):
    hit = np.zeros(len(regions), bool)
    for chrom, g in peaks.groupby("chrom"):
        idx = np.flatnonzero(regions.chrom.to_numpy() == chrom)
        if not len(idx):
            continue
        st, en = regions.start.to_numpy()[idx], regions.end.to_numpy()[idx]
        lo = np.searchsorted(en, g.start.to_numpy(), side="right")  # first region with end > peak start
        hi = np.searchsorted(st, g.end.to_numpy(), side="left")  # regions with start < peak end
        for a, b in zip(lo, hi):
            hit[idx[a:b]] = True
    return hit


def peak_share(regions, peaks):
    reg = regions.copy()
    hits = 0
    for chrom, g in peaks.groupby("chrom"):
        idx = np.flatnonzero(reg.chrom.to_numpy() == chrom)
        st, en = reg.start.to_numpy()[idx], reg.end.to_numpy()[idx]
        lo = np.searchsorted(en, g.start.to_numpy(), side="right")
        hi = np.searchsorted(st, g.end.to_numpy(), side="left")
        hits += int((hi > lo).sum())
    return hits / max(len(peaks), 1)


def main(manifest, out_dir, threads=8):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(manifest, sep="\t")
    atac = m[m.assay == "ATAC"]
    regions = consensus(list(zip(atac["sample"], atac.peaks)))
    regions[["chrom", "start", "end", "region", "n_samples"]].to_csv(out / "regions.bed", sep="\t", index=False,
                                                                       header=False)
    print(f"regions: {len(regions)}; width median {np.median(regions.end - regions.start):.0f}", flush=True)
    with Pool(threads) as p:
        res = p.map(count_bam, [(b, regions) for b in m.bam])
    cnt = pd.DataFrame({s: c for s, (c, _) in zip(m["sample"], res)})
    cnt.insert(0, "region", regions.region)
    cnt.to_csv(out / "counts.tsv.gz", sep="\t", index=False)
    lib = m[["sample", "assay", "time", "rep"]].copy()
    lib["lib_size"] = [x for _, x in res]
    lib["in_regions"] = cnt.drop(columns="region").sum().to_numpy()
    lib["frip"] = lib.in_regions / lib.lib_size
    lib.to_csv(out / "lib_size.tsv", sep="\t", index=False)
    occ = pd.DataFrame(dict(region=regions.region))
    share = []
    for _, r in m[(m.assay != "ATAC") & (m.peaks != ".")].iterrows():
        pk = read_peaks(r.peaks)
        occ[r["sample"]] = overlaps(regions, pk)
        share.append(dict(sample=r["sample"], peaks=len(pk), share_in_universe=peak_share(regions, pk)))
    for (a, t), g in m[(m.assay.isin(["SOX9", "SMARCC1"])) & (m.peaks != ".")].groupby(["assay", "time"]):
        occ[f"{a}_{t}_both"] = occ[list(g["sample"])].all(axis=1)
        occ[f"{a}_{t}_any"] = occ[list(g["sample"])].any(axis=1)
    occ.to_csv(out / "occupancy.tsv.gz", sep="\t", index=False)
    pd.DataFrame(share).to_csv(out / "peaks_in_universe.tsv", sep="\t", index=False)
    print(lib.to_string(index=False))
    print(pd.DataFrame(share).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(int(x) for x in sys.argv[3:4]))
