"""Gate A (Paper-ideas v2.0 plan v0.2): per-protein and per-pair covariates for the co-occupancy benchmark.

usage: 60_gateA_features.py <occupancy.bed.gz> <cooccupancy_v1/all dir> <blacklist.bed.gz> <chrom.sizes>
                            <bins500.npz> <bins_annotation.npz> <study_provenance.tsv> <out_dir> [workers=8]

The protein x 500-bp-bin matrix is rebuilt with build_occupancy() of 12_cooccupancy.py ('all' context, same
proteins as Figure 1E: cooccupancy_v1/all/proteins.tsv), so Jaccard here equals Figure 1E's.
Per protein (over its occupied bins): n_exp, breadth, promoter fraction (TSS <= 1 kb), HOT fraction (bins in the top
1 % by occupied-protein count, as in 12), mean log1p ChIP-Atlas ATAC support, cCRE fraction, mean GC (bins with finite GC); plus the sets
of cell types and studies of its experiments (all experiments of the protein in the experiments table, as in 12).
Per pair: number of shared cell types / studies and their Jaccard. Writes proteins.tsv and pairs.tsv.gz.
"""
import csv
import gzip
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "04a_chipatlas"))
build_occupancy = __import__("12_cooccupancy").build_occupancy


def main(bed, cooc_dir, blp, sizes_path, b500, bann, prov, out_dir, workers=8):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fig1e = pd.read_csv(Path(cooc_dir) / "proteins.tsv", sep="\t")
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as t:
        t.write("gene,Class\n" + "".join(f"{g},{c}\n" for g, c in zip(fig1e.protein, fig1e["class"])))
    X, genes, cls, n_exp, _, offs, _ = build_occupancy(bed, t.name, blp, sizes_path, "all", workers)
    assert genes == sorted(fig1e.protein), "protein universe differs from Figure 1E"
    z, a = np.load(b500), np.load(bann)
    zoff = dict(zip(z["chrom"], z["offset"]))
    # map 12's column index (its own chromosome offsets) to the bins500 genome index
    X = X.tocsc()
    cols = np.flatnonzero(np.diff(X.indptr))
    starts = sorted((o, c) for c, o in offs.items())
    so = np.array([o for o, _ in starts])
    ci = np.searchsorted(so, cols, side="right") - 1
    # alt/random contigs are in Figure 1E's matrix but not in the bin annotation: they count for breadth and HOT,
    # annotation fractions use main-chromosome bins only
    main_c = np.array([starts[k][1] in zoff for k in ci])
    gidx = np.array([zoff.get(starts[k][1], 0) for k in ci]) + cols - so[ci]
    X = X[:, cols].tocsr()
    colsum = np.asarray(X.sum(axis=0)).ravel()
    hot = colsum >= np.quantile(colsum, 0.99)
    gm = gidx[main_c]
    Xm = X[:, np.flatnonzero(main_c)]
    prom = a["tss_dist"][gm] <= 1000
    ccre = a["ccre"][gm] > 0
    gc = a["gc"][gm]
    acc = np.log1p(z["atac_experiments"][gm].astype(np.float64))
    breadth = np.asarray(X.sum(axis=1)).ravel()
    bm = np.asarray(Xm.sum(axis=1)).ravel()

    def mean_over(v, M=Xm, n=bm):
        return np.asarray(M @ v.astype(np.float64)).ravel() / n

    exp_tab = Path(bed).with_name("PMA_chipatlas_hg38_experiments.tsv.gz")
    study = pd.read_csv(prov, sep="\t", usecols=["experiment_id", "study"]).set_index("experiment_id").study.to_dict()
    ct, st = {g: set() for g in genes}, {g: set() for g in genes}
    with gzip.open(exp_tab, "rt") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            g = row["antigen_hgnc_symbol"]
            if g in ct:
                ct[g].add(row["cell_type"])
                st[g].add(study.get(row["experiment_id"], "NA:" + row["experiment_id"]))
    prot = pd.DataFrame(dict(protein=genes, cls=[cls[g] for g in genes], n_exp=[n_exp[g] for g in genes],
                             breadth=breadth, prom_frac=mean_over(prom), hot_frac=mean_over(hot, X, breadth),
                             acc_mean=mean_over(acc), ccre_frac=mean_over(ccre), gc_mean=np.asarray(Xm @ np.nan_to_num(gc).astype(np.float64)).ravel() / np.maximum(
                                 np.asarray(Xm @ np.isfinite(gc).astype(np.float64)).ravel(), 1),
                             n_celltypes=[len(ct[g]) for g in genes], n_studies=[len(st[g]) for g in genes]))
    prot.to_csv(out / "proteins.tsv", sep="\t", index=False, float_format="%.5g")
    sim = pd.read_csv(Path(cooc_dir) / "pair_similarity.tsv.gz", sep="\t")
    sc, ss, jc = [], [], []
    for x, y in zip(sim.protein_a, sim.protein_b):
        i, u = len(ct[x] & ct[y]), len(ct[x] | ct[y])
        sc.append(i); jc.append(i / u if u else 0.0); ss.append(len(st[x] & st[y]))
    sim["shared_celltypes"], sim["celltype_jaccard"], sim["shared_studies"] = sc, jc, ss
    sim.to_csv(out / "pairs.tsv.gz", sep="\t", index=False, float_format="%.5g")
    print(prot.describe().to_string())
    print(f"pairs {len(sim)}; same_complex {int(sim.same_complex.sum())}; HOT bins {int(hot.sum())} of {len(hot)}")


if __name__ == "__main__":
    main(*sys.argv[1:9], *(int(x) for x in sys.argv[9:10]))
