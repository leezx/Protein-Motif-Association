"""Step 4a §14: experiment-level clustering and attribution of binding-pattern variation.

usage: 13_experiment_clustering.py <occupancy.bed.gz> <experiments.tsv.gz> <peak_counts_included.tsv>
                                   <class_annotation_v1_1.csv> <blacklist.bed.gz> <chrom.sizes> <out_dir> [workers]
Design §14: experiments with >= 1,000 peaks; 500-bp bins occupied by >= 20 experiments (random 500,000, seed
20261021); TF-IDF + truncated SVD (50); kNN (10, cosine) label agreement vs expectation; k-means (50) AMI;
controlled views within cell types and within proteins; t-SNE figure.
"""
import array
import collections
import csv
import gzip
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import sparse

BIN = 500
G = {}


def scan_chrom(args):
    chrom, off = args
    exps = G["exps"]
    keys = array.array("q")
    p = subprocess.Popen(["tabix", G["bed"], chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in p.stdout:
        f = line.split("\t", 5)
        ei = exps.get(f[3])
        if ei is None:
            continue
        s, e = int(f[1]), int(f[2])
        for b in range(s // BIN, (e - 1) // BIN + 1):
            keys.append(((off + b) << 16) | ei)
    if p.wait() != 0:
        raise RuntimeError(chrom)
    k = np.unique(np.frombuffer(keys, dtype=np.int64))
    path = f"{G['work']}/{chrom}.npy"
    np.save(path, k)
    b, c = np.unique(k >> 16, return_counts=True)
    return chrom, path, b, c


def attribution(emb_nn, labels, name):
    """Observed fraction of 10-NN sharing a non-missing label vs expectation sum p^2."""
    lab = np.asarray(labels, dtype=object)
    ok = lab != "."
    if ok.sum() < 20:
        return None
    nn = emb_nn
    obs = []
    for i in np.where(ok)[0]:
        nb = [j for j in nn[i] if ok[j]]
        if nb:
            obs.append(np.mean([lab[j] == lab[i] for j in nb]))
    cnt = collections.Counter(lab[ok]); n = ok.sum()
    exp = sum((v / n) ** 2 for v in cnt.values())
    o = float(np.mean(obs))
    return dict(factor=name, n=int(n), n_levels=len(cnt), observed_same_label=round(o, 4),
                expected_same_label=round(exp, 4), enrichment=round(o / exp, 2) if exp else None)


def knn(emb, k=10):
    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=min(k + 1, len(emb)), metric="cosine", algorithm="brute", n_jobs=4).fit(emb)
    return nn.kneighbors(emb, return_distance=False)[:, 1:]


def main(bed, exp_tab, counts, ann, blp, sizes_path, out, workers=4):
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.decomposition import TruncatedSVD
    from sklearn.metrics import adjusted_mutual_info_score
    from sklearn.preprocessing import normalize
    out = Path(out); work = out / "work"; work.mkdir(parents=True, exist_ok=True)
    npk = {l.split("\t")[0]: int(l.split("\t")[1]) for l in open(counts) if not l.startswith("experiment_id")}
    cls = {r["gene"]: r["Class"] for r in csv.DictReader(open(ann, encoding="utf-8-sig"))}
    meta = {}
    with gzip.open(exp_tab, "rt") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if npk.get(r["experiment_id"], 0) >= 1000:
                g = r["antigen_hgnc_symbol"]
                meta[r["experiment_id"]] = dict(
                    protein=g if g != "." else "_".join(r["antigen_raw"].split()),
                    protein_class=cls.get(g, "Non-gene label") if g != "." else "Non-gene label",
                    cell_type=r["cell_type"] or ".", tissue=r["tissue"] or ".",
                    antibody_status=r["antibody_status"] or ".", n_peaks=npk[r["experiment_id"]])
    ids = sorted(meta); exps = {e: i for i, e in enumerate(ids)}
    assert len(ids) < 1 << 16
    sizes = {l.split("\t")[0]: int(l.split("\t")[1]) for l in Path(sizes_path).read_text().splitlines() if l}
    chroms = [c for c in subprocess.run(["tabix", "-l", bed], capture_output=True, text=True, check=True).stdout.split()
              if c in sizes and (not os.environ.get("PMA_CHROMS") or c in os.environ["PMA_CHROMS"].split(","))]
    offs, o = {}, 0
    for c in chroms:
        offs[c] = o; o += sizes[c] // BIN + 1
    G.update(bed=bed, exps=exps, work=str(work))
    bl = []
    with gzip.open(blp, "rt") as f:
        for l in f:
            c, s, e = l.split("\t")[:3]
            if c in offs:
                bl.extend(range(offs[c] + int(s) // BIN, offs[c] + (int(e) - 1) // BIN + 1))
    bl = np.unique(np.array(bl, dtype=np.int64))
    paths, bins, cnts = [], [], []
    with mp.Pool(workers) as pool:
        for chrom, path, b, c in pool.imap_unordered(scan_chrom, [(c, offs[c]) for c in chroms]):
            paths.append(path); bins.append(b); cnts.append(c)
    b = np.concatenate(bins); c = np.concatenate(cnts)
    cand = b[(c >= 20) & ~np.isin(b, bl)]
    rng = np.random.default_rng(20261021)
    feat = np.sort(rng.choice(cand, size=min(500000, len(cand)), replace=False))
    rows, cols = [], []
    for path in paths:
        k = np.load(path)
        kb = k >> 16
        pos = np.searchsorted(feat, kb)
        hit = (pos < len(feat)) & (feat[np.minimum(pos, len(feat) - 1)] == kb)
        rows.append((k[hit] & 0xFFFF).astype(np.int64)); cols.append(pos[hit])
        Path(path).unlink()
    work.rmdir()
    r_ = np.concatenate(rows); c_ = np.concatenate(cols)
    X = sparse.csr_matrix((np.ones(len(r_), dtype=np.float32), (r_, c_)), shape=(len(ids), len(feat)))
    rs = np.asarray(X.sum(axis=1)).ravel(); keep = rs > 0
    X = X[keep]; ids = [e for e, k in zip(ids, keep) if k]; rs = rs[keep]
    cs = np.asarray(X.sum(axis=0)).ravel()
    idf = np.log1p(X.shape[0] / np.maximum(cs, 1)).astype(np.float32)
    T = sparse.diags(1.0 / rs) @ X
    T.data = np.log1p(T.data * 1e4)
    T = T @ sparse.diags(idf)
    svd = TruncatedSVD(n_components=50, algorithm="randomized", random_state=20261021)
    Z = svd.fit_transform(T)
    depth = np.log10([meta[e]["n_peaks"] for e in ids])
    corr = [float(np.corrcoef(Z[:, i], depth)[0, 1]) for i in range(Z.shape[1])]
    keepc = [i for i, r in enumerate(corr) if abs(r) <= 0.7]
    E = normalize(Z[:, keepc])
    np.savez_compressed(out / "embedding.npz", Z=Z, ids=np.array(ids), depth=depth, corr=np.array(corr))
    with open(out / "svd_depth_correlation.tsv", "w") as w:
        w.write("component\texplained_variance_ratio\tr_log10_peaks\tkept\n")
        for i, r in enumerate(corr):
            w.write(f"{i + 1}\t{svd.explained_variance_ratio_[i]:.5f}\t{r:.3f}\t{i in keepc}\n")
    dec = np.digitize(depth, np.quantile(depth, np.linspace(0.1, 0.9, 9)))
    for e, d in zip(ids, dec):
        meta[e]["peak_decile"] = f"D{d + 1}"
    factors = ["protein", "protein_class", "cell_type", "tissue", "peak_decile", "antibody_status"]
    nn = knn(E)
    km = MiniBatchKMeans(n_clusters=50, random_state=20261021, n_init=5, batch_size=4096).fit(E)
    att = []
    for fct in factors:
        lab = [meta[e][fct] for e in ids]
        a = attribution(nn, lab, fct)
        ok = np.array([x != "." for x in lab])
        a["ami_kmeans50"] = round(float(adjusted_mutual_info_score(np.array(lab)[ok], km.labels_[ok])), 4)
        a["view"] = "all"; att.append(a)
    # controlled views
    ctrl = []
    top_ct = [c for c, _ in collections.Counter(meta[e]["cell_type"] for e in ids).most_common() if c != "."][:2]
    prot_counts = collections.Counter(meta[e]["protein"] for e in ids
                                      if meta[e]["protein_class"] != "Non-gene label")
    views = [("cell_type", c, ["protein", "protein_class", "peak_decile"]) for c in ["K-562", "Hep G2"] + top_ct]
    views += [("protein", p, ["cell_type", "tissue", "peak_decile"]) for p in
              ["CTCF"] + [p for p, _ in prot_counts.most_common(4) if p != "CTCF"][:3]]
    seen = set()
    for key, val, fs in views:
        if (key, val) in seen:
            continue
        seen.add((key, val))
        sub = [i for i, e in enumerate(ids) if meta[e][key] == val]
        if len(sub) < 30:
            continue
        nn_s = knn(E[sub])
        for fct in fs:
            a = attribution(nn_s, [meta[ids[i]][fct] for i in sub], fct)
            if a:
                a["view"] = f"{key}={val}"; ctrl.append(a)
    with open(out / "attribution.tsv", "w") as w:
        cols_ = ["view", "factor", "n", "n_levels", "observed_same_label", "expected_same_label", "enrichment", "ami_kmeans50"]
        w.write("\t".join(cols_) + "\n")
        for a in att + ctrl:
            w.write("\t".join(str(a.get(k, ".")) for k in cols_) + "\n")
    with open(out / "clusters.tsv", "w") as w:
        w.write("experiment_id\tcluster\t" + "\t".join(factors) + "\tn_peaks\n")
        for e, k in zip(ids, km.labels_):
            w.write(f"{e}\tK{k:02d}\t" + "\t".join(str(meta[e][f]) for f in factors) + f"\t{meta[e]['n_peaks']}\n")
    # t-SNE figure
    from sklearn.manifold import TSNE
    Y = TSNE(n_components=2, init="pca", perplexity=30, random_state=20261021, n_jobs=4).fit_transform(E)
    np.savetxt(out / "tsne.tsv", Y, delimiter="\t", fmt="%.4f")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(20, 9.5))
    for ax, fct, top in ((axs[0], "protein_class", 8), (axs[1], "cell_type", 12)):
        lab = np.array([meta[e][fct] for e in ids])
        tops = [c for c, _ in collections.Counter(lab).most_common(top) if c != "."]
        ax.scatter(Y[:, 0], Y[:, 1], s=1, c="#d0d0d0", lw=0, rasterized=True)
        cmap = plt.get_cmap("tab20")
        for i, c in enumerate(tops):
            m = lab == c
            ax.scatter(Y[m, 0], Y[m, 1], s=1.5, color=cmap(i % 20), lw=0, label=f"{c} ({m.sum()})", rasterized=True)
        ax.legend(markerscale=6, fontsize=7, loc="upper right"); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"ChIP-Atlas protein experiments (n={len(ids):,}), coloured by {fct}")
    fig.tight_layout(); fig.savefig(out / "tsne.png", dpi=170); plt.close(fig)
    summ = dict(experiments=len(ids), features=int(len(feat)), candidate_bins=int(len(cand)),
                components_kept=len(keepc), attribution={a["factor"]: (a["enrichment"], a["ami_kmeans50"]) for a in att})
    (out / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:7], workers=int(a[7]) if len(a) > 7 else 4)
