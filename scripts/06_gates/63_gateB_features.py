"""Gate B (plan v0.2 B5, B6): pre-perturbation features for every region of the baseline-only universe.

usage: 63_gateB_features.py <gateB out_root> <experiments.tsv.gz> <atac_occupancy.bed.gz> <genes.gtf> <rna TPM.csv>
                            <cutrun narrowPeak dir> [threads=8]
       63_gateB_features.py matrices <gateB out_root> <experiments.tsv.gz>     (occupancy matrices only)

Reads <root>/counts (62), <root>/pma (46, 50). Writes <root>/features/:
  features.tsv.gz      region-level baseline covariates (B0-B2 inputs; nothing from D2-D13)
  pma_binary.mtx       region x protein occupancy, non-HT-29 experiments (rows = regions.bed order); proteins.tsv
  pma_binary_gut.mtx   same, digestive-tract non-HT-29 experiments; proteins_gut.tsv
PMA occupancy of protein p in region R: n(R, p) >= k_p = max(2, ceil(0.05 N_p)) experiments, N_p = experiments of p
outside HT-29 (gut: floor 1, N_p over digestive-tract non-HT-29 experiments). Proteins are kept when N_p >= 2 and they
occupy >= 500 universe regions (gut: N_p >= 1, >= 100 regions). The SVD embedding is fitted per outer fold in
64_gateB_model.R (preflight fix 2), not here.
HOT-like degree = occupied proteins; coverage = log1p(sum of non-HT-29 experiments).
External ATAC prior = share of non-HT-29 ChIP-Atlas ATAC experiments with a peak overlapping the region.
RNA: DMSO log2(TPM + 1), mean of 2 replicates, of the gene (protein-coding or lncRNA) whose TSS is nearest.
"""
import gzip
import math
import re
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.io import mmwrite

def binary(pairs, col, tot, floor, min_regions, nreg):
    p = pairs[pairs[col] > 0]
    n_p = p.target.map(tot).fillna(0)
    kp = np.maximum(floor, np.ceil(0.05 * n_p))
    p = p[(n_p >= floor) & (p[col] >= kp)]
    cnt = p.target.value_counts()
    keep = sorted(cnt.index[cnt >= min_regions])
    p = p[p.target.isin(keep)]
    j = pd.Index(keep).get_indexer(p.target)
    B = sparse.csr_matrix((np.ones(len(p), np.float32), (p.ridx.to_numpy(), j)), shape=(nreg, len(keep)))
    return B, keep


def atac_prior(args):
    bed, chrom, reg = args
    st, en = reg.start.to_numpy(), reg.end.to_numpy()
    hit_other, hit_ht = [set() for _ in st], [set() for _ in st]
    seen_other = set()
    proc = subprocess.Popen(["tabix", bed, chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in proc.stdout:
        f = line.split("\t", 15)
        s, e, srx, ct = int(f[1]), int(f[2]), f[3], f[13]
        ht = ct == "HT-29"
        if not ht:
            seen_other.add(srx)
        i = np.searchsorted(st, e, side="left") - 1
        while i >= 0 and en[i] > s - 5000:
            if st[i] < e and en[i] > s:
                (hit_ht if ht else hit_other)[i].add(srx)
            i -= 1
    proc.wait()
    return chrom, [len(x) for x in hit_other], [len(x) for x in hit_ht], seen_other


def gene_tss(gtf):
    rows = []
    with open(gtf) as f:
        for l in f:
            if l.startswith("#"):
                continue
            x = l.split("\t")
            if x[2] != "gene":
                continue
            gt = re.search(r'gene_type "([^"]+)"', x[8]).group(1)
            if gt not in ("protein_coding", "lncRNA"):
                continue
            gid = re.search(r'gene_id "([^".]+)', x[8]).group(1)
            rows.append((x[0], int(x[3]) - 1 if x[6] == "+" else int(x[4]) - 1, gid))
    return pd.DataFrame(rows, columns=["chrom", "tss", "gene_id"]).sort_values(["chrom", "tss"])


def main(root, exp_tab, atac_bed, gtf, tpm_csv, peak_dir, threads=8):
    root = Path(root)
    out = root / "features"
    out.mkdir(exist_ok=True)
    reg = pd.read_csv(root / "counts/regions.bed", sep="\t", header=None,
                      names=["chrom", "start", "end", "region", "n_samples"])
    nreg = len(reg)
    f = reg[["region", "chrom", "start", "end"]].copy()
    ann = pd.read_csv(root / "pma/annotation.tsv.gz", sep="\t")
    f = f.merge(ann[["region", "ccre", "tss_dist", "cpg", "gc", "blacklist"]], on="region", how="left")
    sox = pd.read_csv(root / "pma/sox_motifs.tsv.gz", sep="\t")
    f = f.merge(sox, on="region", how="left")
    # HT29 baseline signal (DMSO, both replicates) as log2 CPM of counted fragments
    cnt = pd.read_csv(root / "counts/counts.tsv.gz", sep="\t")
    lib = pd.read_csv(root / "counts/lib_size.tsv", sep="\t").set_index("sample").lib_size
    for name, a in (("atac", "{}"), ("sox9", "DMSO_SOX9_{}"), ("smarcc1", "DMSO_SMARCC1_{}"),
                    ("h3k27ac", "DMSO_H3K27Ac_{}"), ("h3k4me3", "DMSO_H3K4me3_{}"), ("igg", "DMSO_IgG_{}")):
        cols = [a.format(f"DMSO_{r}") if name == "atac" else a.format(r) for r in (1, 2)]
        cpm = np.column_stack([cnt[c] / lib[c] * 1e6 for c in cols])
        f[f"{name}_log2cpm"] = np.log2(cpm.mean(axis=1) + 0.5).round(4)
    occ = pd.read_csv(root / "counts/occupancy.tsv.gz", sep="\t")
    for c in ("SOX9_DMSO_both", "SOX9_DMSO_any", "SMARCC1_DMSO_both", "SMARCC1_DMSO_any"):
        f[c.lower()] = occ[c].to_numpy()
    # SOX9 DMSO peak strength: max MACS signalValue of overlapping peaks, mean over replicates (0 when none)
    sv = []
    for r in (1, 2):
        pk = pd.read_csv(Path(peak_dir) / f"DMSO_SOX9_{r}.sorted.mapped.bam_peaks.narrowPeak", sep="\t", header=None,
                         usecols=[0, 1, 2, 6], names=["chrom", "s", "e", "sig"])
        v = np.zeros(nreg)
        for chrom, g in reg.groupby("chrom"):
            p = pk[pk.chrom == chrom].sort_values("s")
            ps, pe, sg = p.s.to_numpy(), p.e.to_numpy(), p.sig.to_numpy()
            for i, s, e in zip(g.index, g.start, g.end):
                j = np.searchsorted(ps, e)
                k = j - 1
                m = 0.0
                while k >= 0 and ps[k] > s - 20000:
                    if pe[k] > s:
                        m = max(m, sg[k])
                    k -= 1
                v[i] = m
        sv.append(v)
    f["sox9_peak_signal"] = np.mean(sv, axis=0).round(3)
    # external ATAC prior without HT-29
    with Pool(threads) as pool:
        res = pool.map(atac_prior, [(atac_bed, c, g.reset_index(drop=True)) for c, g in reg.groupby("chrom", sort=False)])
    n_other = len(set().union(*[r[3] for r in res]))
    pri = pd.concat([pd.DataFrame(dict(region=reg[reg.chrom == c].region.to_numpy(), o=o, h=h)) for c, o, h, _ in res])
    f = f.merge(pri, on="region", how="left")
    f["ext_atac_frac"] = (f.pop("o") / n_other).round(5)
    f["ext_atac_ht29_n"] = f.pop("h")
    # RNA: nearest protein-coding / lncRNA TSS
    tss = gene_tss(gtf)
    tpm = pd.read_csv(tpm_csv, index_col=0)
    tpm.index = tpm.index.str.split("_").str[0]
    expr = np.log2(tpm[["DMSO_1", "DMSO_2"]] + 1).mean(axis=1)
    mid = ((f.start + f.end) // 2).to_numpy()
    g_id, g_d = np.empty(nreg, object), np.zeros(nreg, np.int64)
    for chrom, idx in f.groupby("chrom").groups.items():
        t = tss[tss.chrom == chrom]
        tp, ti = t.tss.to_numpy(), t.gene_id.to_numpy()
        m = mid[idx]
        j = np.clip(np.searchsorted(tp, m), 1, len(tp) - 1)
        best = np.where(np.abs(tp[j - 1] - m) <= np.abs(tp[j] - m), j - 1, j)
        g_id[idx], g_d[idx] = ti[best], np.abs(tp[best] - m)
    f["near_gene"], f["near_gene_dist"] = g_id, g_d
    f["near_gene_log2tpm"] = pd.Series(g_id).map(expr).fillna(0).round(4).to_numpy()
    # PMA reference without HT-29
    e = pd.read_csv(exp_tab, sep="\t", usecols=["experiment_id", "antigen_class", "antigen_raw", "antigen_hgnc_symbol",
                                                "cell_type", "cell_type_class"])
    e = e[e.antigen_class.isin(["TFs and others", "RNA polymerase"])].drop_duplicates("experiment_id")
    e["target"] = np.where(e.antigen_hgnc_symbol.fillna(".") != ".", e.antigen_hgnc_symbol,
                           e.antigen_raw.astype(str).str.replace(r"\s+", "_", regex=True))
    e = e[e.cell_type != "HT-29"]
    tot = e.target.value_counts()
    tot_gut = e[e.cell_type_class == "Digestive tract"].target.value_counts()
    pairs = pd.read_csv(root / "pma/pairs.tsv.gz", sep="\t")
    pairs["ridx"] = pd.Index(reg.region).get_indexer(pairs.region)
    pairs["n_nonht"] = pairs.n_exp - pairs.n_exp_ht29
    pairs["n_gut_nonht"] = pairs.n_exp_gut - pairs.n_exp_ht29
    B, prots = binary(pairs, "n_nonht", tot, 2, 500, nreg)
    Bg, prots_g = binary(pairs, "n_gut_nonht", tot_gut, 1, 100, nreg)
    deg = np.asarray(B.sum(axis=1)).ravel()
    f["pma_degree"] = deg
    cov = pairs.groupby("ridx").n_nonht.sum()
    f["pma_coverage"] = np.log1p(cov.reindex(range(nreg)).fillna(0).to_numpy()).round(4)
    f.to_csv(out / "features.tsv.gz", sep="\t", index=False)
    write_matrices(out, B, Bg, prots, prots_g, tot, tot_gut)
    print(f"regions {nreg}; proteins {len(prots)} (gut {len(prots_g)}); non-HT-29 ATAC experiments {n_other}; "
          f"regions with HT-29 ATAC peak {(f.ext_atac_ht29_n > 0).sum()}; SOX9-bound (both) {f.sox9_dmso_both.sum()}")


def write_matrices(out, B, Bg, prots, prots_g, tot, tot_gut):
    mmwrite(out / "pma_binary.mtx", B)
    mmwrite(out / "pma_binary_gut.mtx", Bg)
    pd.DataFrame(dict(protein=prots, regions=np.asarray(B.sum(axis=0)).ravel().astype(int),
                      n_exp_nonht29=[int(tot[p]) for p in prots])).to_csv(out / "proteins.tsv", sep="\t", index=False)
    pd.DataFrame(dict(protein=prots_g, regions=np.asarray(Bg.sum(axis=0)).ravel().astype(int),
                      n_exp_gut_nonht29=[int(tot_gut[p]) for p in prots_g])).to_csv(out / "proteins_gut.tsv", sep="\t",
                                                                                     index=False)


def matrices_only(root, exp_tab):
    """Rebuild only the two occupancy matrices (same rules as main)."""
    root = Path(root)
    reg = pd.read_csv(root / "counts/regions.bed", sep="\t", header=None,
                      names=["chrom", "start", "end", "region", "n_samples"])
    e = pd.read_csv(exp_tab, sep="\t", usecols=["experiment_id", "antigen_class", "antigen_raw", "antigen_hgnc_symbol",
                                                "cell_type", "cell_type_class"])
    e = e[e.antigen_class.isin(["TFs and others", "RNA polymerase"])].drop_duplicates("experiment_id")
    e["target"] = np.where(e.antigen_hgnc_symbol.fillna(".") != ".", e.antigen_hgnc_symbol,
                           e.antigen_raw.astype(str).str.replace(r"\s+", "_", regex=True))
    e = e[e.cell_type != "HT-29"]
    tot, tot_gut = e.target.value_counts(), e[e.cell_type_class == "Digestive tract"].target.value_counts()
    pairs = pd.read_csv(root / "pma/pairs.tsv.gz", sep="\t")
    pairs["ridx"] = pd.Index(reg.region).get_indexer(pairs.region)
    pairs["n_nonht"] = pairs.n_exp - pairs.n_exp_ht29
    pairs["n_gut_nonht"] = pairs.n_exp_gut - pairs.n_exp_ht29
    B, prots = binary(pairs, "n_nonht", tot, 2, 500, len(reg))
    Bg, prots_g = binary(pairs, "n_gut_nonht", tot_gut, 1, 100, len(reg))
    write_matrices(root / "features", B, Bg, prots, prots_g, tot, tot_gut)
    print(f"proteins {len(prots)}; gut {len(prots_g)}; nnz {B.nnz} / {Bg.nnz}")


if __name__ == "__main__":
    if sys.argv[1] == "matrices":
        matrices_only(*sys.argv[2:4])
    else:
        main(*sys.argv[1:7], *(int(x) for x in sys.argv[7:8]))
