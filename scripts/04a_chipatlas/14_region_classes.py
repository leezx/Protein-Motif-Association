"""Step 4a §15: region-level occupancy classes from the §13 protein x bin occupancy (context 'all').

usage: 14_region_classes.py <occupancy.bed.gz> <class_annotation_v1_1.csv> <blacklist.bed.gz> <chrom.sizes>
                            <out_dir> [workers]
Bins occupied by >= 3 selected proteins; TF-IDF + truncated SVD (30); MiniBatch k-means k in {10, 20, 30} with a
50,000-bin silhouette; k = 20 unless another k beats it by > 0.05. Writes classes.tsv, class_proteins.tsv,
silhouette.tsv and region_classes.bed.gz (+ .tbi, .bb; adjacent bins of one class merged; name = class).
"""
import collections
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import sparse

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("cooc", HERE / "12_cooccupancy.py")
cooc = importlib.util.module_from_spec(_spec); sys.modules["cooc"] = cooc; _spec.loader.exec_module(cooc)
BIN = cooc.BIN


def main(bed, ann, blp, sizes_path, out, workers=5):
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.decomposition import TruncatedSVD
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import normalize
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    X, genes, cls, n_exp, floor, offs, sizes = cooc.build_occupancy(bed, ann, blp, sizes_path, "all", workers)
    B = X.T.tocsr()  # bins x proteins
    npb = np.asarray(B.sum(axis=1)).ravel()
    occ = npb > 0
    hot_cut = np.quantile(npb[occ], 0.99)
    sel = np.where(npb >= 3)[0]
    Bs = B[sel]; nps = npb[sel]
    idf = np.log1p(Bs.shape[0] / np.maximum(np.asarray(Bs.sum(axis=0)).ravel(), 1)).astype(np.float32)
    T = sparse.diags(1.0 / nps) @ Bs
    T.data = np.log1p(T.data * 1e4)
    T = T @ sparse.diags(idf)
    Z = normalize(TruncatedSVD(n_components=30, algorithm="randomized", random_state=20261021).fit_transform(T))
    rng = np.random.default_rng(20261021)
    samp = rng.choice(len(sel), size=min(50000, len(sel)), replace=False)
    fits, sil = {}, {}
    for k in (10, 20, 30):
        km = MiniBatchKMeans(n_clusters=k, random_state=20261021, n_init=5, batch_size=8192).fit(Z)
        fits[k] = km.labels_; sil[k] = float(silhouette_score(Z[samp], km.labels_[samp]))
    best = max(sil, key=sil.get)
    k = best if sil[best] - sil[20] > 0.05 else 20
    lab = fits[k]
    with open(out / "silhouette.tsv", "w") as w:
        w.write("k\tsilhouette_50k\tchosen\n")
        for kk in sorted(sil):
            w.write(f"{kk}\t{sil[kk]:.4f}\t{kk == k}\n")
    # order classes by size
    order = [c for c, _ in collections.Counter(lab).most_common()]
    name = {c: f"C{i + 1:02d}" for i, c in enumerate(order)}
    overall = np.asarray(Bs.mean(axis=0)).ravel()
    classes = ["Sequence-specific TF", "Architectural/cohesin", "Chromatin remodeler", "Histone reader",
               "Histone writer/eraser", "Transcription machinery"]
    gcls = np.array([cls[g] for g in genes])
    rows_c, rows_p = [], []
    for c in order:
        m = lab == c
        sub = Bs[m]
        frac = np.asarray(sub.mean(axis=0)).ravel()
        enr = np.where(overall > 0, frac / np.maximum(overall, 1e-9), 0)
        top = [i for i in np.argsort(-enr) if frac[i] >= 0.10][:15]
        comp = {}
        tot = sub.sum()
        for cl in classes:
            comp[cl] = round(float(sub[:, np.where(gcls == cl)[0]].sum() / max(tot, 1)), 3)
        rows_c.append(dict(cls=name[c], bins=int(m.sum()), median_proteins=float(np.median(nps[m])),
                           hot_fraction=round(float((nps[m] >= hot_cut).mean()), 3),
                           top_proteins=";".join(f"{genes[i]}({frac[i]:.2f},x{enr[i]:.1f})" for i in top), **comp))
        for i in top:
            rows_p.append(dict(cls=name[c], protein=genes[i], protein_class=cls[genes[i]], in_class_fraction=round(float(frac[i]), 3),
                               overall_fraction=round(float(overall[i]), 4), enrichment=round(float(enr[i]), 2)))
    for fn, rows in (("classes.tsv", rows_c), ("class_proteins.tsv", rows_p)):
        with open(out / fn, "w") as w:
            w.write("\t".join(rows[0]) + "\n")
            for r in rows:
                w.write("\t".join(map(str, r.values())) + "\n")
    # BED of classified bins, adjacent same-class bins merged
    inv = sorted(offs.items(), key=lambda x: x[1]); starts = np.array([o for _, o in inv])
    chrom_names = [c for c, _ in inv]
    gb = sel
    ci = np.searchsorted(starts, gb, side="right") - 1
    bedp = out / "region_classes.bed"
    with open(bedp, "w") as w:
        cur = None
        for g, cix, l, n in zip(gb, ci, lab, nps):
            c = chrom_names[cix]; s = (g - starts[cix]) * BIN; e = min(s + BIN, sizes[c])
            if cur and cur[0] == c and cur[2] == s and cur[3] == name[l]:
                cur[2] = e; cur[4] = max(cur[4], n)
            else:
                if cur:
                    w.write(f"{cur[0]}\t{cur[1]}\t{cur[2]}\t{cur[3]}\t{min(1000, int(cur[4]))}\t.\n")
                cur = [c, s, e, name[l], n]
        if cur:
            w.write(f"{cur[0]}\t{cur[1]}\t{cur[2]}\t{cur[3]}\t{min(1000, int(cur[4]))}\t.\n")
    subprocess.run(["bash", "-c", f"LC_ALL=C sort -k1,1 -k2,2n {bedp} -o {bedp}"], check=True)
    subprocess.run(["bedToBigBed", "-type=bed6", "-tab", str(bedp), sizes_path, str(out / "region_classes.bb")], check=True)
    subprocess.run(["bgzip", "-f", str(bedp)], check=True)
    subprocess.run(["tabix", "-f", "-p", "bed", str(bedp) + ".gz"], check=True)
    summ = dict(proteins=len(genes), bins_occupied=int(occ.sum()), bins_classified=int(len(sel)), hot_cut=float(hot_cut),
                silhouette=sil, k=k, classes=[{kk: r[kk] for kk in ("cls", "bins", "median_proteins", "hot_fraction")}
                                              for r in rows_c])
    (out / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ)[:3000])


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:5], workers=int(a[5]) if len(a) > 5 else 5)
