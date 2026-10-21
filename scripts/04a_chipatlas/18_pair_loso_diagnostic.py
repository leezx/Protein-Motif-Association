"""Diagnostic: per-study LOSO Jaccard for one protein pair, same rules as 16_cooccupancy_validation.py.

usage: 18_pair_loso_diagnostic.py <scripts_dir> <occupancy.bed.gz> <class_annotation_v1_1.csv> <blacklist> <chrom.sizes>
                                  <study_provenance.tsv> <protein_A> <protein_B>
"""
import collections, csv, gzip, importlib.util, sys
from pathlib import Path
import multiprocessing as mp
import numpy as np
code, bed, ann, blp, sizes, study_tsv, A, B = sys.argv[1:9]
spec = importlib.util.spec_from_file_location("val", Path(code) / "16_cooccupancy_validation.py")
v = importlib.util.module_from_spec(spec); sys.modules["val"] = v; spec.loader.exec_module(v)
X, genes, cls, n_exp, floor, offs, sz = v.cooc.build_occupancy(bed, ann, blp, sizes, "all", 8)
colsum = np.asarray(X.sum(axis=0)).ravel(); uni = colsum > 0
valid = uni & (colsum < np.quantile(colsum[uni], 0.99))
study = {r["experiment_id"]: r["study"] for r in csv.DictReader(open(study_tsv), delimiter="\t")}
idx = {A: 0, B: 1}; exps = {}; ep = []
with gzip.open(Path(bed).with_name("PMA_chipatlas_hg38_experiments.tsv.gz"), "rt") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["antigen_hgnc_symbol"] in idx and r["experiment_id"] not in exps:
            exps[r["experiment_id"]] = len(ep); ep.append((r["experiment_id"], idx[r["antigen_hgnc_symbol"]]))
v.G.update(bed=bed, prot=idx, exps=exps)
with mp.Pool(8) as pool:
    K = np.sort(np.concatenate(pool.map(v.scan, list(offs.items()))))
pk = K >> 40
be = [v.decode(K[pk == 0]), v.decode(K[pk == 1])]
ep_p = np.array([p for _, p in ep]); ep_s = np.array([study.get(e, "single:" + e) for e, _ in ep])
def J(m):
    na, nb = int((m & (ep_p == 0)).sum()), int((m & (ep_p == 1)).sum())
    a, b = v.occ_bins(be[0], m, na, valid), v.occ_bins(be[1], m, nb, valid)
    return v.jac(a, b), na, nb, len(a), len(b)
allm = np.ones(len(ep), bool)
print("full", J(allm))
cnt = collections.Counter(zip(ep_s, ep_p))
rows = []
for s in sorted(set(ep_s)):
    j = J(allm & (ep_s != s))
    rows.append((j[0], s, cnt[(s, 0)], cnt[(s, 1)]) + j[1:])
rows.sort()
print("lowest LOSO: jaccard study nA_in_study nB_in_study nA_left nB_left binsA binsB")
for r in rows[:10]: print(*r)
