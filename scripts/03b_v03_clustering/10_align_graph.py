"""Step 3b §15: alignment-weighted candidate graph.

usage: 10_align_graph.py <K>   (K = 100, or 200 on the pre-allowed fallback)
Per partition:
1. exact top-K neighbours in PCA space (PCs 1:30, Euclidean, blocked BLAS);
   candidates = union over both directions.
2. recall check (must pass): candidates contain >= 95 % of the v0.2.1
   both-direction match pairs (Step 3 edges.tsv.gz, same partition) and >= 90 %
   within each source family and each length stratum.
3. s for every candidate pair; edges with s >= 0.65 (weight s).
4. connected components of the edge graph.
Outputs (result/step3b_v03/align/): edges_<part>.tsv.gz (i, j, s; node index =
row of pca/nodes_<part>.tsv), recall_k<K>.tsv, align_summary_k<K>.json
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.csgraph import connected_components

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_align as pa  # noqa: E402
import pma_motif as pm  # noqa: E402

DIMS, EDGE_S = 30, 0.65
R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3b_v03"
S3 = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3_motif_clustering"
OUT = R / "align"
QB = 2048
LEN_BINS = [0, 8, 12, 16, 20, 1000]


def knn(X, k):
    """Exact Euclidean top-k (self excluded) in query blocks."""
    n = len(X)
    sq = (X * X).sum(1)
    nb = np.empty((n, k), dtype=np.int64)
    for a in range(0, n, QB):
        q = X[a:a + QB]
        d = sq[a:a + QB, None] - 2 * q @ X.T + sq[None, :]
        d[np.arange(len(q)), np.arange(a, a + len(q))] = np.inf
        p = np.argpartition(d, k, axis=1)[:, :k]
        nb[a:a + QB] = p
    return nb


def main(k):
    OUT.mkdir(parents=True, exist_ok=True)
    nodes = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t")
    md = pd.read_csv(Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_raw_layer" / "PMA_motif_metadata.tsv",
                     sep="\t", low_memory=False, usecols=["pma_id", "source_db"])
    fam = nodes.merge(md, on="pma_id").groupby("node_id").source_db.agg(
        lambda s: s.value_counts().sort_index().idxmax())
    e3 = pd.read_csv(S3 / "edges.tsv.gz", sep="\t", usecols=["a", "b"], dtype=str)
    summ, rec_rows = {"K": k}, []
    for part in ("composite", "monomer"):
        ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
        idx = {n: i for i, n in enumerate(ids)}
        X = pd.read_csv(R / "pca" / f"pca_{part}.tsv.gz", sep="\t").set_index("node_id").reindex(ids)
        X = np.ascontiguousarray(X.iloc[:, :DIMS].to_numpy(dtype=np.float32))
        kk = min(k, len(ids) - 1)
        nb = knn(X, kk)
        a = np.repeat(np.arange(len(ids)), kk)
        b = nb.ravel()
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        pair = np.unique(lo.astype(np.int64) * len(ids) + hi)
        pi, pj = pair // len(ids), pair % len(ids)
        # recall vs v0.2.1 both-direction matches within this partition
        ea, eb = e3.a.map(idx), e3.b.map(idx)
        ok = ea.notna() & eb.notna()
        ea, eb = ea[ok].astype(int).to_numpy(), eb[ok].astype(int).to_numpy()
        key = np.minimum(ea, eb).astype(np.int64) * len(ids) + np.maximum(ea, eb)
        hit = np.isin(key, pair)
        mats = {n: m for n, p, m in pm.read_meme(R / "nodes" / "nodes.meme") if p == part}
        Z, Zrc, st, ln = pa.pack([mats[n] for n in ids])
        lshort = np.minimum(ln[ea], ln[eb])
        r = pd.DataFrame({"hit": hit, "fam": fam.reindex(ids[ea]).to_numpy(),
                          "len": pd.cut(lshort, LEN_BINS).astype(str)})
        overall = float(hit.mean()) if len(hit) else np.nan
        for col in ("fam", "len"):
            for g, d in r.groupby(col):
                rec_rows.append(dict(part=part, stratum_type=col, stratum=g, n=len(d), recall=float(d.hit.mean())))
        strata = [x for x in rec_rows if x["part"] == part and x["n"] >= 500]
        passed = bool(len(hit) == 0 or (overall >= 0.95 and all(x["recall"] >= 0.90 for x in strata)))
        # alignment edges
        s = pa.s_pairs(Z, Zrc, st, ln, pi.astype(np.int64), pj.astype(np.int64))
        keep = s >= EDGE_S
        ed = pd.DataFrame({"i": pi[keep], "j": pj[keep], "s": s[keep]})
        ed.to_csv(OUT / f"edges_{part}_k{k}.tsv.gz", sep="\t", index=False, float_format="%.5g")
        g = sparse.coo_matrix((np.ones(len(ed)), (ed.i, ed.j)), shape=(len(ids), len(ids)))
        ncomp, lab = connected_components(g, directed=False)
        sizes = np.bincount(lab)
        summ[part] = dict(nodes=len(ids), candidate_pairs=int(len(pair)), edges=int(keep.sum()),
                          recall_pairs=int(len(hit)), recall_overall=overall, recall_pass=passed,
                          components=int(ncomp), singletons=int((sizes == 1).sum()),
                          largest_component=int(sizes.max()), s_quantiles=np.quantile(s, [.1, .5, .9]).round(3).tolist())
        print(part, json.dumps(summ[part]), flush=True)
    pd.DataFrame(rec_rows).to_csv(OUT / f"recall_k{k}.tsv", sep="\t", index=False, float_format="%.4f")
    summ["recall_pass_all"] = all(summ[p]["recall_pass"] for p in ("composite", "monomer"))
    summ["K_total_floor"] = summ["composite"]["components"] + summ["monomer"]["components"]
    (OUT / f"align_summary_k{k}.json").write_text(json.dumps(summ, indent=2) + "\n")
    print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
