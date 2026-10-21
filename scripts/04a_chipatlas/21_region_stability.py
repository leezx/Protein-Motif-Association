"""Step 4a §17 C: stability of the §15 region classes.

usage: 21_region_stability.py <occupancy.bed.gz> <class_annotation_v1_1.csv> <blacklist.bed.gz> <chrom.sizes>
                              <out_dir> [workers]
Same features as 14_region_classes.py (bins with >= 3 proteins, TF-IDF, SVD 30, MiniBatch k-means). Reports:
cross-resolution agreement (k = 10/20/30), 5 extra seeds at k = 20, 5 x 80 % bin subsamples, and non-HOT
re-clustering (ARI/NMI on shared bins), plus per-class best-match Jaccard against every rerun.
"""
import collections
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("cooc", HERE / "12_cooccupancy.py")
cooc = importlib.util.module_from_spec(_spec); sys.modules["cooc"] = cooc; _spec.loader.exec_module(cooc)
SEED = 20261021


def embed(Bs, nps, seed):
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize
    idf = np.log1p(Bs.shape[0] / np.maximum(np.asarray(Bs.sum(axis=0)).ravel(), 1)).astype(np.float32)
    T = sparse.diags(1.0 / nps) @ Bs
    T.data = np.log1p(T.data * 1e4)
    T = T @ sparse.diags(idf)
    return normalize(TruncatedSVD(n_components=30, algorithm="randomized", random_state=seed).fit_transform(T))


def km(Z, k, seed):
    from sklearn.cluster import MiniBatchKMeans
    return MiniBatchKMeans(n_clusters=k, random_state=seed, n_init=5, batch_size=8192).fit(Z).labels_


def best_match(a, b):
    """For each label of a: max Jaccard with any label of b (a, b on the same items)."""
    out = {}
    for la in np.unique(a):
        ma = a == la; sa = ma.sum(); best = 0.0
        for lb, inter in collections.Counter(b[ma]).items():
            best = max(best, inter / (sa + (b == lb).sum() - inter))
        out[int(la)] = best
    return out


def main(bed, ann, blp, sizes_path, out, workers=5):
    from sklearn.metrics import adjusted_rand_score as ari, normalized_mutual_info_score as nmi
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    X, genes, cls, *_ = cooc.build_occupancy(bed, ann, blp, sizes_path, "all", workers)
    B = X.T.tocsr(); npb = np.asarray(B.sum(axis=1)).ravel()
    hot_cut = np.quantile(npb[npb > 0], 0.99)
    sel = np.where(npb >= 3)[0]; Bs = B[sel]; nps = npb[sel]
    Z = embed(Bs, nps, SEED)
    base = {k: km(Z, k, SEED) for k in (10, 20, 30)}
    lab = base[20]
    order = [c for c, _ in collections.Counter(lab).most_common()]
    name = {c: f"C{i + 1:02d}" for i, c in enumerate(order)}
    res = {"bins": int(len(sel)), "class_sizes": {name[c]: int((lab == c).sum()) for c in order}}
    res["cross_resolution"] = {f"{a}v{b}": dict(ari=round(ari(base[a], base[b]), 4), nmi=round(nmi(base[a], base[b]), 4))
                               for a, b in ((10, 20), (20, 30), (10, 30))}
    per_class = collections.defaultdict(dict)
    for k in (10, 30):
        for c, j in best_match(lab, base[k]).items():
            per_class[name[c]][f"k{k}"] = round(j, 3)
    runs = {}
    for s in range(1, 6):
        Zs = embed(Bs, nps, SEED + s)
        runs[f"seed{s}"] = (np.arange(len(sel)), km(Zs, 20, SEED + s))
    rng = np.random.default_rng(SEED)
    for r in range(5):
        sub = np.sort(rng.choice(len(sel), int(0.8 * len(sel)), replace=False))
        runs[f"sub80_{r}"] = (sub, km(Z[sub], 20, SEED + 100 + r))
    nh = np.where(nps < hot_cut)[0]
    runs["nohot"] = (nh, km(embed(Bs[nh], nps[nh], SEED), 20, SEED))
    res["reruns"] = {}
    for key, (items, l2) in runs.items():
        l1 = lab[items]
        res["reruns"][key] = dict(n=int(len(items)), ari=round(ari(l1, l2), 4), nmi=round(nmi(l1, l2), 4))
        for c, j in best_match(l1, l2).items():
            per_class[name[c]][key] = round(j, 3)
    rows = []
    for c in order:
        d = per_class[name[c]]; rr = [v for kk, v in d.items() if kk not in ("k10", "k30")]
        rows.append(dict(cls=name[c], bins=int((lab == c).sum()), median_best_match_reruns=round(float(np.median(rr)), 3),
                         min_best_match_reruns=round(float(np.min(rr)), 3), k10=d.get("k10"), k30=d.get("k30"),
                         nohot=d.get("nohot")))
    with open(out / "region_stability.tsv", "w") as w:
        w.write("\t".join(rows[0]) + "\n")
        for r in rows:
            w.write("\t".join(str(v) for v in r.values()) + "\n")
    # class composition (to compare with region_classes_v1/classes.tsv)
    overall = np.asarray(Bs.mean(axis=0)).ravel(); comp = {}
    for c in order:
        frac = np.asarray(Bs[lab == c].mean(axis=0)).ravel()
        top = np.argsort(-frac)[:5]
        comp[name[c]] = [f"{genes[i]}({frac[i]:.2f},x{frac[i] / max(overall[i], 1e-9):.1f})" for i in top]
    res["class_top_proteins"] = comp
    res["per_class"] = rows
    (out / "summary.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in ("cross_resolution", "reruns")}, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:5], workers=int(a[5]) if len(a) > 5 else 5)
