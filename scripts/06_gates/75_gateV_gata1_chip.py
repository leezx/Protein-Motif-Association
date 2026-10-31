"""Gate V feasibility: K562 GATA1 ChIP-Atlas support for each Spear-ATAC peak (the 'true occupancy' analogue of
HT29 SOX9 CUT&RUN). Uses only unperturbed K-562 GATA1 experiments (qc_flags without 'perturbed_sample').

usage: 75_gateV_gata1_chip.py <occupancy.bed.gz> <experiments.tsv.gz> <peaks.bed.gz> <out.tsv.gz>
Writes peak index, n GATA1 experiments with a peak overlapping it (>= 1 bp) and the number of eligible experiments.
"""
import gzip
import subprocess
import sys

import numpy as np
import pandas as pd


def main(bed, exp_tab, peaks, out):
    e = pd.read_csv(exp_tab, sep="\t", usecols=["experiment_id", "antigen_hgnc_symbol", "cell_type", "qc_flags"])
    e = e[(e.cell_type == "K-562") & (e.antigen_hgnc_symbol == "GATA1") & ~e.qc_flags.astype(str).str.contains("perturbed")]
    ok = set(e.experiment_id)
    p = pd.read_csv(peaks, sep="\t", header=None, names=["chrom", "start", "end"])
    n = np.zeros(len(p), np.int32)
    for chrom, g in p.groupby("chrom"):
        st, en, idx = g.start.to_numpy(), g.end.to_numpy(), g.index.to_numpy()
        o = np.argsort(st); st, en, idx = st[o], en[o], idx[o]
        hits = [set() for _ in range(len(st))]
        proc = subprocess.Popen(["tabix", bed, chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
        for line in proc.stdout:
            f = line.split("\t", 10)
            if f[3] not in ok:
                continue
            s, t = int(f[1]), int(f[2])
            j = np.searchsorted(st, t) - 1
            while j >= 0 and en[j] > s - 1000:
                if st[j] < t and en[j] > s:
                    hits[j].add(f[3])
                j -= 1
        proc.wait()
        n[idx] = [len(h) for h in hits]
    pd.DataFrame(dict(peak=np.arange(len(p)), gata1_n_exp=n, gata1_n_eligible=len(ok))).to_csv(out, sep="\t", index=False)
    print(f"eligible GATA1 K562 experiments {len(ok)}; peaks {len(p)}; >=1 {int((n >= 1).sum())}; >=2 {int((n >= 2).sum())}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
