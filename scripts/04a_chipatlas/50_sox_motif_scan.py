"""SOX-family PWM scores for the HT29 consensus regions (Context Query v0.1, GPT review item: motif-adjusted SOX test).

usage: 50_sox_motif_scan.py <regions.bed> <motifs.meme> <genome.fa> <out.tsv.gz> [p=1e-4]

Motifs: HOCOMOCO v14 CORE.0 for SOX9, SOX10, SOX8, SOX13, SOX5, SOX6 (the SOX targets of the PMA ranking). Per
region and motif, with the scan of 46_ht29_pma_evidence.py (log-odds, uniform background, both strands): n hits with
P < p and the best score minus the P < p threshold (bits; > 0 means a hit). Summary columns: sox_motif_hits (sum over
motifs), sox_motif_margin (max over motifs of best - threshold).
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MOTIFS = {"SOX9": "HO14_SOX9.H14CORE.0.PS.A", "SOX10": "HO14_SOX10.H14CORE.0.PSM.A",
          "SOX8": "HO14_SOX8.H14CORE.0.PSM.A", "SOX13": "HO14_SOX13.H14CORE.0.P.B",
          "SOX5": "HO14_SOX5.H14CORE.0.P.B", "SOX6": "HO14_SOX6.H14CORE.0.P.B"}

spec = importlib.util.spec_from_file_location("ev46", Path(__file__).with_name("46_ht29_pma_evidence.py"))
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def main(regions, meme, fasta, out, p=1e-4):
    reg = ev.load_regions(regions)
    d = reg[["region"]].copy()
    for tf, mid in MOTIFS.items():
        n_hit, best, thr = ev.motif_scan(reg, fasta, ev.read_meme(meme, mid), p)
        d[f"{tf}_hits"], d[f"{tf}_margin"] = n_hit, best - thr
        print(f"{tf} {mid}: threshold {thr:.2f}; regions with hit {(n_hit > 0).mean():.3f}", flush=True)
    d["sox_motif_hits"] = d[[f"{t}_hits" for t in MOTIFS]].sum(axis=1)
    d["sox_motif_margin"] = d[[f"{t}_margin" for t in MOTIFS]].max(axis=1)
    d.to_csv(out, sep="\t", index=False)
    print(d.drop(columns="region").corr(method="spearman").round(2).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:5], *(float(x) for x in sys.argv[5:6]))
