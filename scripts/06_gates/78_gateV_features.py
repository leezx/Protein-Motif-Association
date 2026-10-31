"""Gate V (contract paper_ideas_v2_gateV_contract): per-peak features for the Spear-ATAC K562 peaks.

usage: 78_gateV_features.py regions <inventory/peaks.bed.gz> <gateV root>
       78_gateV_features.py features <gateV root> <atac_occupancy.bed.gz> <histone_occupancy.bed.gz> <experiments.tsv.gz> [threads=8]

regions: writes <root>/counts/regions.bed (chrom, start, end, region P######, 0) in peak order, the input of 46 / 50.
features (run with PMA_EXCL_CELL=K-562 so 63's helpers exclude K562): external ATAC prior = share of non-K-562
ChIP-Atlas ATAC experiments with a peak overlapping the region (63.atac_prior); K562 histone support = share of
unperturbed K-562 H3K27ac / H3K4me3 experiments with an overlapping peak; PMA occupancy matrices without K-562
(63.matrices_only: same k_p rule and protein filter as Gate B). Writes <root>/features/features.tsv.gz and the
matrices. Annotation (GC, CpG, TSS, cCRE, blacklist) comes from 46 annotate, GATA motifs from 50 (PMA_MOTIFS).
"""
import os
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
m63 = __import__("63_gateB_features")
MARKS = ("H3K27ac", "H3K4me3")
EXCL = os.environ.get("PMA_EXCL_CELL", "K-562")


def regions(peaks, root):
    p = pd.read_csv(peaks, sep="\t", header=None, names=["chrom", "start", "end"])
    p["region"] = [f"P{i:06d}" for i in range(len(p))]
    p["n"] = 0
    (Path(root) / "counts").mkdir(parents=True, exist_ok=True)
    p.to_csv(Path(root) / "counts/regions.bed", sep="\t", header=False, index=False)
    print("regions", len(p))


def histone(args):
    bed, chrom, reg, ok = args
    st, en = reg.start.to_numpy(), reg.end.to_numpy()
    hits = {m: [set() for _ in st] for m in MARKS}
    proc = subprocess.Popen(["tabix", bed, chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in proc.stdout:
        f = line.split("\t", 15)
        if f[3] not in ok:
            continue
        s, e, mk = int(f[1]), int(f[2]), f[7]
        i = np.searchsorted(st, e, side="left") - 1
        while i >= 0 and en[i] > s - 5000:
            if st[i] < e and en[i] > s:
                hits[mk][i].add(f[3])
            i -= 1
    proc.wait()
    return chrom, {m: [len(h) for h in hits[m]] for m in MARKS}


def features(root, atac_bed, hist_bed, exp_tab, threads=8):
    root = Path(root)
    reg = pd.read_csv(root / "counts/regions.bed", sep="\t", header=None, names=["chrom", "start", "end", "region", "n"])
    with Pool(threads) as pool:
        res = pool.map(m63.atac_prior, [(atac_bed, c, g.reset_index(drop=True)) for c, g in reg.groupby("chrom", sort=False)])
    n_other = len(set().union(*[r[3] for r in res]))
    pri = pd.concat([pd.DataFrame(dict(region=reg[reg.chrom == c].region.to_numpy(), ext_atac_n=o, ext_atac_k562_n=h))
                     for c, o, h, _ in res])
    # unperturbed K-562 histone experiments per mark (histone layer: column 8 = mark, 14 = cell type, last = qc flags)
    out = subprocess.run(f"zcat {hist_bed} | awk -F'\\t' '$14==\"{EXCL}\" && ($8==\"H3K27ac\" || $8==\"H3K4me3\") "
                         f"&& $24 !~ /perturbed/ {{print $4\"\\t\"$8}}' | sort -u", shell=True, capture_output=True, text=True,
                         check=True).stdout
    tab = pd.DataFrame([l.split("\t") for l in out.splitlines()], columns=["experiment_id", "mark"])
    ok = set(tab.experiment_id)
    tot = tab.mark.value_counts().to_dict()
    with Pool(threads) as pool:
        hres = pool.map(histone, [(hist_bed, c, g.reset_index(drop=True), ok) for c, g in reg.groupby("chrom", sort=False)])
    h = pd.concat([pd.DataFrame(dict(region=reg[reg.chrom == c].region.to_numpy(),
                                     **{f"k562_{m.lower()}_frac": np.array(v[m]) / tot.get(m, 1) for m in MARKS}))
                   for c, v in hres])
    f = reg[["region", "chrom", "start", "end"]].merge(pri, on="region").merge(h, on="region")
    f["ext_atac_frac"] = (f.pop("ext_atac_n") / n_other).round(5)
    (root / "features").mkdir(exist_ok=True)
    f.to_csv(root / "features/features.tsv.gz", sep="\t", index=False)
    m63.matrices_only(root, exp_tab)
    print(f"regions {len(f)}; non-{EXCL} ATAC experiments {n_other}; {EXCL} histone experiments {tot}")


if __name__ == "__main__":
    if sys.argv[1] == "regions":
        regions(*sys.argv[2:4])
    else:
        features(*sys.argv[2:6], *(int(x) for x in sys.argv[6:7]))
