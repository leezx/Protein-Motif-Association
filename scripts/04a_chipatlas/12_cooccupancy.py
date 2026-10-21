"""Step 4a §13: protein-level co-occupancy (DBP modules) with a known-complex benchmark.

usage: 12_cooccupancy.py <occupancy.bed.gz> <class_annotation_v1_1.csv> <blacklist.bed.gz> <chrom.sizes>
                         <complexportal_9606.tsv> <hgnc_complete_set.txt> <out_dir> [context] [workers]
context: 'all' (default) or a ChIP-Atlas cell type (column 14, e.g. 'K-562').
Definitions and thresholds: design §13. Bins are 500 bp; occupancy needs k_p = max(floor, ceil(0.05 n_exp(p)))
distinct experiments (floor 2 for 'all', 1 within one cell type).
"""
import array
import collections
import csv
import gzip
import json
import math
import multiprocessing as mp
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform

BIN = 500
CLASSES = {"Sequence-specific TF", "Architectural/cohesin", "Chromatin remodeler", "Histone reader",
           "Histone writer/eraser", "Transcription machinery"}
NAMED = {"cohesin+CTCF": ["CTCF", "RAD21", "SMC1A", "SMC3", "STAG1", "STAG2"],
         "BAF": ["SMARCA4", "SMARCA2", "SMARCC1", "SMARCC2", "SMARCB1", "ARID1A", "ARID1B", "SMARCE1", "SMARCD1"],
         "Mediator": None, "PRC2": ["EZH2", "SUZ12", "EED", "JARID2", "MTF2"],
         "NuRD": ["CHD4", "HDAC1", "HDAC2", "MTA1", "MTA2", "MTA3", "GATAD2A", "GATAD2B", "MBD3"]}
G = {}  # set in main, inherited by workers


def scan_chrom(chrom):
    """int64 keys (protein << 40 | bin << 16 | experiment) of distinct (p, bin, e) on one chromosome."""
    prot, exps, ctx = G["prot"], G["exps"], G["context"]
    keys = array.array("q")
    p = subprocess.Popen(["tabix", G["bed"], chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in p.stdout:
        f = line.split("\t", 15)
        pi = prot.get(f[8])
        if pi is None or (ctx != "all" and f[13] != ctx):
            continue
        ei = exps.get(f[3])
        if ei is None:
            continue
        s, e = int(f[1]), int(f[2])
        for b in range(s // BIN, (e - 1) // BIN + 1):
            keys.append((pi << 40) | (b << 16) | ei)
    if p.wait() != 0:
        raise RuntimeError(chrom)
    k = np.unique(np.frombuffer(keys, dtype=np.int64))
    pb = k >> 16  # (protein, bin)
    u, cnt = np.unique(pb, return_counts=True)
    return chrom, u, cnt


def load_blacklist(path, sizes):
    bl = collections.defaultdict(set)
    with gzip.open(path, "rt") as f:
        for l in f:
            c, s, e = l.split("\t")[:3]
            for b in range(int(s) // BIN, (int(e) - 1) // BIN + 1):
                bl[c].add(b)
    return bl


def complexes(cp_path, hgnc_path, keep):
    uni = {}
    with open(hgnc_path, encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            for u in (row.get("uniprot_ids") or "").split("|"):
                if u:
                    uni[u.strip('"')] = row["symbol"]
    out = {}
    with open(cp_path, encoding="utf-8") as f:
        r = csv.reader(f, delimiter="\t")
        hdr = next(r)
        ix = hdr.index("Expanded participant list") if "Expanded participant list" in hdr else 4
        for row in r:
            genes = set()
            for m in re.finditer(r"([A-Z0-9]{6,10})(?:-\d+)?\(", row[ix]):
                g = uni.get(m.group(1))
                if g in keep:
                    genes.add(g)
            if len(genes) >= 2:
                out[f"{row[0]} {row[1]}"] = sorted(genes)
    return out


def auroc(pos, neg):
    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort() + 1.0
    # average ranks for ties
    order = np.argsort(allv, kind="mergesort"); sv = allv[order]; r = np.empty_like(ranks)
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2 + 1; i = j + 1
    rp = r[:len(pos)].sum()
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def heatmap(mat, names, cls, order, path, title, vmin, vmax, cmap):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(order)
    pal = {"Sequence-specific TF": "#1f4e9b", "Architectural/cohesin": "#7a3e91", "Chromatin remodeler": "#2a9d8f",
           "Histone reader": "#e9a03b", "Histone writer/eraser": "#d1495b", "Transcription machinery": "#6c757d"}
    fig = plt.figure(figsize=(14, 13))
    ax_c = fig.add_axes([0.06, 0.06, 0.012, 0.86]); ax = fig.add_axes([0.075, 0.06, 0.86, 0.86])
    ax_b = fig.add_axes([0.945, 0.3, 0.012, 0.4])
    m = mat[np.ix_(order, order)]
    im = ax.imshow(m, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest", aspect="auto")
    from matplotlib.colors import ListedColormap
    keys = list(pal)
    ax_c.imshow(np.array([[keys.index(cls[names[i]])] for i in order]), cmap=ListedColormap([pal[k] for k in keys]),
                aspect="auto", interpolation="nearest", vmin=0, vmax=len(keys) - 1)
    ax_c.set_xticks([]); ax_c.set_yticks([])
    ax.set_xticks([]); ax.set_yticks([])
    if n <= 150:
        ax.set_yticks(range(n)); ax.set_yticklabels([names[i] for i in order], fontsize=4); ax.yaxis.tick_right()
    fig.colorbar(im, cax=ax_b)
    for i, k in enumerate(keys):
        fig.text(0.06 + i * 0.15, 0.03, "■ " + k, color=pal[k], fontsize=8)
    fig.suptitle(title, fontsize=11)
    fig.savefig(path, dpi=200); plt.close(fig)


def build_occupancy(bed, ann, blp, sizes_path, context="all", workers=5):
    """Protein x 500-bp-bin occupancy (design §13): returns X (csr), genes, cls, n_exp, floor, offs, sizes."""
    cls = {r["gene"]: r["Class"] for r in csv.DictReader(open(ann, encoding="utf-8-sig")) if r["Class"] in CLASSES}
    # experiments per protein in this context (from the BED annotation via the experiments table next to v1)
    exp_tab = Path(bed).with_name("PMA_chipatlas_hg38_experiments.tsv.gz")
    n_exp = collections.Counter(); exps = {}
    with gzip.open(exp_tab, "rt") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            g = row["antigen_hgnc_symbol"]
            if g in cls and (context == "all" or row["cell_type"] == context) and row["experiment_id"] not in exps:
                exps[row["experiment_id"]] = len(exps); n_exp[g] += 1
    floor = 2 if context == "all" else 1
    min_exp = 3 if context == "all" else 2
    genes = sorted(g for g in cls if n_exp[g] >= min_exp)
    prot = {g: i for i, g in enumerate(genes)}
    kp = np.array([max(floor, math.ceil(0.05 * n_exp[g])) for g in genes])
    assert len(exps) < 1 << 16 and len(genes) < 1 << 23
    sizes = {l.split("\t")[0]: int(l.split("\t")[1]) for l in Path(sizes_path).read_text().splitlines() if l}
    chroms = [c for c in subprocess.run(["tabix", "-l", bed], capture_output=True, text=True, check=True).stdout.split()
              if c in sizes and (not os.environ.get("PMA_CHROMS") or c in os.environ["PMA_CHROMS"].split(","))]
    G.update(bed=bed, prot=prot, exps=exps, context=context)
    bl = load_blacklist(blp, sizes)
    offs, o = {}, 0
    for c in chroms:
        offs[c] = o; o += sizes[c] // BIN + 1
    rows, cols = [], []
    with mp.Pool(workers) as pool:
        for chrom, u, cnt in pool.imap_unordered(scan_chrom, sorted(chroms, key=lambda c: -sizes[c])):
            pi = (u >> 24).astype(np.int64); b = (u & ((1 << 24) - 1)).astype(np.int64)
            ok = cnt >= kp[pi]
            if bl.get(chrom):
                blm = np.isin(b, np.fromiter(bl[chrom], dtype=np.int64))
                ok &= ~blm
            rows.append(pi[ok]); cols.append(b[ok] + offs[chrom])
    r_ = np.concatenate(rows); c_ = np.concatenate(cols)
    X = sparse.csr_matrix((np.ones(len(r_), dtype=np.float32), (r_, c_)), shape=(len(genes), o))
    size = np.asarray(X.sum(axis=1)).ravel()
    keep = np.where(size >= 500)[0]
    X = X[keep]; genes = [genes[i] for i in keep]; size = size[keep]
    return X, genes, cls, n_exp, floor, offs, sizes


def main(bed, ann, blp, sizes_path, cp, hgnc, out, context="all", workers=5):
    out = Path(out) / re.sub(r"[^A-Za-z0-9]+", "_", context); out.mkdir(parents=True, exist_ok=True)
    X, genes, cls, n_exp, floor, offs, sizes = build_occupancy(bed, ann, blp, sizes_path, context, workers)
    colsum = np.asarray(X.sum(axis=0)).ravel()
    universe = colsum > 0
    hot_cut = np.quantile(colsum[universe], 0.99)
    res = {}
    for label, mask in (("all_bins", universe), ("noHOT", universe & (colsum < hot_cut))):
        Xm = X[:, np.where(mask)[0]]
        a = np.asarray(Xm.sum(axis=1)).ravel()
        inter = (Xm @ Xm.T).toarray()
        union = a[:, None] + a[None, :] - inter
        J = np.where(union > 0, inter / np.maximum(union, 1), 0.0)
        N = mask.sum()
        oe = np.log2(np.maximum(inter, 0.5) * N / np.maximum(np.outer(a, a), 1))
        np.fill_diagonal(J, 1.0); np.fill_diagonal(oe, np.nan)
        res[label] = (J, oe, a, N)
    J, oe, a, N = res["all_bins"]
    # clustering
    link_j = hierarchy.linkage(squareform(1 - J, checks=False), "average")
    d_oe = np.nan_to_num(np.nanmax(oe) - oe, nan=0.0); np.fill_diagonal(d_oe, 0)
    link_o = hierarchy.linkage(squareform(d_oe, checks=False), "average")
    order_j = hierarchy.leaves_list(link_j); order_o = hierarchy.leaves_list(link_o)
    names = genes
    heatmap(J, names, cls, order_j, out / "heatmap_jaccard.png",
            f"ChIP-Atlas DBP co-occupancy, Jaccard ({context}; {len(names)} proteins; {N:,} bins)", 0, 0.5, "magma_r")
    oe_plot = np.nan_to_num(oe, nan=np.nanmax(oe))
    heatmap(oe_plot, names, cls, order_o, out / "heatmap_log2oe.png",
            f"ChIP-Atlas DBP co-occupancy, log2 O/E ({context}; {len(names)} proteins)", -2, 4, "RdBu_r")
    # benchmark
    cpx = complexes(cp, hgnc, set(names))
    idx = {g: i for i, g in enumerate(names)}
    same = set()
    for gs in cpx.values():
        for i in range(len(gs)):
            for j in range(i + 1, len(gs)):
                same.add(tuple(sorted((idx[gs[i]], idx[gs[j]]))))
    iu = np.triu_indices(len(names), 1)
    bench = {"context": context, "proteins": len(names), "universe_bins": int(N), "hot_cut_proteins": float(hot_cut),
             "complexes_with_2plus_members": len(cpx), "same_complex_pairs": len(same)}
    rng = np.random.default_rng(20261021)
    for label, (Jm, oem, _, _) in res.items():
        flag = np.array([(i, j) in same for i, j in zip(*iu)])
        for mname, M in (("jaccard", Jm), ("log2oe", oem)):
            v = M[iu]
            if flag.sum() and (~flag).sum():
                bench[f"auroc_{mname}_{label}"] = round(float(auroc(v[flag], v[~flag])), 4)
    rec = []
    named = dict(NAMED); named["Mediator"] = [g for g in names if re.match(r"^MED\d", g)]
    allsets = list(cpx.items()) + [(f"named:{k}", [g for g in v if g in idx]) for k, v in named.items()]
    for nm, gs in allsets:
        gs = [g for g in gs if g in idx]
        if len(gs) < 2:
            continue
        ii = [idx[g] for g in gs]
        sub = J[np.ix_(ii, ii)][np.triu_indices(len(ii), 1)]
        subo = oe[np.ix_(ii, ii)][np.triu_indices(len(ii), 1)]
        null_o, null_j = [], []
        for _ in range(1000):
            rr = rng.choice(len(names), len(ii), replace=False)
            tri = np.triu_indices(len(rr), 1)
            null_o.append(np.median(oe[np.ix_(rr, rr)][tri])); null_j.append(np.median(J[np.ix_(rr, rr)][tri]))
        null_o = np.array(null_o); null_j = np.array(null_j)
        med_o = float(np.median(subo)); med_j = float(np.median(sub))
        rec.append(dict(complex=nm, n_members_present=len(gs), members=";".join(gs),
                        median_jaccard=round(med_j, 4), null_median_jaccard=round(float(np.median(null_j)), 4),
                        empirical_p_jaccard=round(float((1 + (null_j >= med_j).sum()) / 1001), 4),
                        median_log2oe=round(med_o, 3), null_median_log2oe=round(float(np.median(null_o)), 3),
                        empirical_p_log2oe=round(float((1 + (null_o >= med_o).sum()) / 1001), 4)))
    rec.sort(key=lambda x: (not x["complex"].startswith("named:"), x["empirical_p_jaccard"]))
    with open(out / "complex_recovery.tsv", "w") as w:
        w.write("\t".join(rec[0]) + "\n")
        for x in rec:
            w.write("\t".join(map(str, x.values())) + "\n")
    real = [x for x in rec if not x["complex"].startswith("named:")]
    bench["complexes_tested"] = len(real)
    for m in ("jaccard", "log2oe"):
        bench[f"complexes_p_le_0.05_{m}"] = sum(x[f"empirical_p_{m}"] <= 0.05 for x in real)
    bench["named"] = {x["complex"]: {k: x[k] for k in ("n_members_present", "median_jaccard", "null_median_jaccard",
                                                       "empirical_p_jaccard", "median_log2oe", "empirical_p_log2oe")}
                      for x in rec if x["complex"].startswith("named:")}
    (out / "benchmark.json").write_text(json.dumps(bench, indent=1) + "\n")
    with open(out / "proteins.tsv", "w") as w:
        w.write("protein\tclass\tn_experiments\tk_threshold\toccupied_bins\tcluster_order_jaccard\n")
        pos = {g: k for k, g in enumerate(names[i] for i in order_j)}
        for i, g in enumerate(names):
            w.write(f"{g}\t{cls[g]}\t{n_exp[g]}\t{max(floor, math.ceil(0.05 * n_exp[g]))}\t{int(a[i])}\t{pos[g]}\n")
    with gzip.open(out / "pair_similarity.tsv.gz", "wt") as w:
        w.write("protein_a\tprotein_b\tjaccard\tlog2oe\tjaccard_noHOT\tlog2oe_noHOT\tsame_complex\n")
        Jh, oeh = res["noHOT"][0], res["noHOT"][1]
        for i, j in zip(*iu):
            w.write(f"{names[i]}\t{names[j]}\t{J[i, j]:.4f}\t{oe[i, j]:.3f}\t{Jh[i, j]:.4f}\t{oeh[i, j]:.3f}\t{(i, j) in same}\n")
    np.savetxt(out / "linkage_jaccard.tsv", link_j, delimiter="\t", fmt="%.6g")
    print(json.dumps({k: v for k, v in bench.items() if k != "named"}))
    print(json.dumps(bench["named"]))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:7], context=a[7] if len(a) > 7 else "all", workers=int(a[8]) if len(a) > 8 else 5)
