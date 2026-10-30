"""Noise ceiling for the hotspot context analysis: experiment-pair agreement within vs between cell types.

usage: 35_context_replicate.py <experiments.tsv.gz> <class_annotation.csv> <context_dir>

Uses the outputs of 32_hotspot_context.py (parts/, breadth.tsv) for top1 bins only, and only cell types where the
bin is active. For bin b, target p, cell type c: n = experiments of p in c, k = those with a peak at b.
Pairs of experiments of the same target at the same bin, counted only when at least one of the pair has a peak:
  within  c:        agree = C(k, 2),  pairs = C(n, 2) - C(n - k, 2)          (cells with n >= 2)
  between c1 != c2: agree = k1 * k2,  pairs = n1 * n2 - (n1 - k1) * (n2 - k2)
Two weightings: pooled = sum agree / sum pairs (dominated by targets with many experiments in one cell type);
unit = per (bin, target), within = mean over its cells of agree / pairs, between = mean over its cell pairs, then
averaged over units where both are defined (every bin x target counts once). Targets without an HGNC symbol
(Epitope_tags, GFP, ...) are excluded: one label covers many proteins. If between ~ within, cross-cell-type
differences are no larger than replicate noise. 'matched' = only cells with >= 2 experiments of the target, so both
sides use the same cells. Writes replicate_agreement.tsv.
"""
import collections
import csv
import glob
import gzip
import sys
from pathlib import Path

COFACTOR = {"Transcription machinery", "Histone writer/eraser", "Histone reader", "Chromatin remodeler",
            "Architectural/cohesin"}


def main(exps, ann_csv, ctx):
    ctx = Path(ctx)
    nexp = collections.Counter()
    with gzip.open(exps, "rt") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            t = "_".join((r["antigen_hgnc_symbol"] if r["antigen_hgnc_symbol"] != "." else r["antigen_raw"]).split())
            nexp[(r["cell_type"], t)] += 1
    dbp, cls = set(), {}
    with open(ann_csv) as f:
        for r in csv.DictReader(f):
            cls[r["gene"]] = r["Class"]
            if "lambert2018_TF" in r["functional_tags"].split(";"):
                dbp.add(r["gene"])

    def group(t):
        return "DBP" if t in dbp else ("cofactor" if cls.get(t) in COFACTOR else "other")

    active = {}
    with open(ctx / "breadth.tsv") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["group"] == "top1" and r["active_celltypes"]:
                active[int(r["bin_id"])] = r["active_celltypes"].split(",")
    hits = collections.defaultdict(dict)  # bin -> (cell, target) -> k
    for p in glob.glob(str(ctx / "parts/*.tsv")):
        with open(p) as f:
            for line in f:
                b, c, t, k = line.rstrip("\n").split("\t")
                b = int(b)
                if b in active:
                    hits[b][(c, t)] = int(k)
    acc = collections.defaultdict(lambda: [0, 0, 0, 0])  # (group, matched) -> within agree, pairs, between agree, pairs
    unit = collections.defaultdict(lambda: [0.0, 0.0, 0])  # (group, matched) -> sum within, sum between, units
    c2 = lambda x: x * (x - 1) // 2
    for b, A in active.items():
        h = hits[b]
        targets = {t for (c, t) in h if c in A and t in cls}
        for t in targets:
            cells = [(c, nexp[(c, t)], h.get((c, t), 0)) for c in A if nexp[(c, t)] > 0]
            rep = [x for x in cells if x[1] >= 2]
            for matched in (False, True):
                if matched and len(rep) < 2:
                    continue
                cs = rep if matched else cells
                v = acc[(group(t), matched)]
                wr, br = [], []
                for c, n, k in cs:
                    if n >= 2 and c2(n) - c2(n - k):
                        v[0] += c2(k)
                        v[1] += c2(n) - c2(n - k)
                        wr.append(c2(k) / (c2(n) - c2(n - k)))
                for i in range(len(cs)):
                    for j in range(i + 1, len(cs)):
                        _, n1, k1 = cs[i]
                        _, n2, k2 = cs[j]
                        d = n1 * n2 - (n1 - k1) * (n2 - k2)
                        if d:
                            v[2] += k1 * k2
                            v[3] += d
                            br.append(k1 * k2 / d)
                if wr and br:
                    u = unit[(group(t), matched)]
                    u[0] += sum(wr) / len(wr); u[1] += sum(br) / len(br); u[2] += 1
    with open(ctx / "replicate_agreement.tsv", "w") as f:
        f.write("group\ttargets\tweighting\tn\twithin_agreement\tbetween_agreement\tratio_between_within\n")
        for (g, m), (wa, wp, ba, bp) in sorted(acc.items()):
            w, bt = wa / wp, ba / bp
            f.write(f"{g}\t{'matched' if m else 'all'}\tpooled\t{wp}\t{w:.4f}\t{bt:.4f}\t{bt / w:.3f}\n")
            sw, sb, nu = unit[(g, m)]
            if nu:
                f.write(f"{g}\t{'matched' if m else 'all'}\tunit\t{nu}\t{sw / nu:.4f}\t{sb / nu:.4f}\t{sb / sw:.3f}\n")
    print(open(ctx / "replicate_agreement.tsv").read())


if __name__ == "__main__":
    main(*sys.argv[1:4])
