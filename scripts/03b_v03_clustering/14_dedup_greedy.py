"""Step 3b (PI 2026-10-17): near-identical redundancy removal before any clustering.

PI direction: motifs that are the same pattern (e.g. one motif present in five
databases) are merged into ONE unique record with an internal ID; every source
record and its annotation is kept and listed against that ID.

Method (CD-HIT-style greedy, no chaining): nodes sorted by priority
  1. evidence v2 tier <= 2 (in vitro / curated core) first
  2. more independent experiments
  3. higher total IC
  4. node ID
Walk the list; an unassigned node becomes the representative of a new unique
motif and absorbs every still-unassigned node with exact alignment similarity
s >= t to it. Every member is therefore within t of its representative.
Similarities come from the exact all-vs-all run (align/exact_<part>_*.npz,
all pairs with s >= 0.65). Partitions are processed separately.

usage: 14_dedup_greedy.py scan            -> dedup/scan.tsv (compression per t, per source)
       14_dedup_greedy.py apply <t>       -> dedup/PMA_unique_motifs_t<t>.tsv,
                                             dedup/PMA_motif_to_unique_t<t>.tsv
"""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
gt = importlib.import_module("05_gates")
R = gt.R
A = R / "align"
D = R / "dedup"
SCAN_T = [0.99, 0.98, 0.97, 0.95, 0.925, 0.90, 0.85]


def load(part):
    ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
    z = [np.load(f) for f in sorted(A.glob(f"exact_{part}_*of*.npz"))]
    q = np.concatenate([x["q"] for x in z]).astype(np.int64)
    t = np.concatenate([x["t"] for x in z]).astype(np.int64)
    s = np.concatenate([x["s"] for x in z])
    return ids, q, t, s


def priority(ids):
    meta, nodes, _ = gt.node_meta(ids)
    key = pd.DataFrame({"h": ~meta.high.to_numpy(), "e": -meta.n_exp.to_numpy(), "i": -meta.ic.to_numpy(),
                        "n": ids})
    return np.lexsort((key.n, key.i, key.e, key.h)), meta, nodes


def greedy(n, q, t, s, thr, order):
    keep = s >= thr
    a, b = q[keep], t[keep]
    g = sparse.csr_matrix((np.ones(len(a) * 2, dtype=np.int8), (np.r_[a, b], np.r_[b, a])), shape=(n, n))
    rep = np.full(n, -1, dtype=np.int64)
    for i in order:
        if rep[i] >= 0:
            continue
        rep[i] = i
        nb = g.indices[g.indptr[i]:g.indptr[i + 1]]
        nb = nb[rep[nb] < 0]
        rep[nb] = i
    return rep


def scan():
    D.mkdir(parents=True, exist_ok=True)
    rows = []
    for part in ("composite", "monomer"):
        ids, q, t, s = load(part)
        order, meta, _ = priority(ids)
        fam = meta.family.to_numpy()
        for thr in SCAN_T:
            rep = greedy(len(ids), q, t, s, thr, order)
            u = len(np.unique(rep))
            rows.append(dict(part=part, t=thr, nodes=len(ids), unique=u, compression=round(u / len(ids), 4),
                             reps_high_evidence=int(meta.high.to_numpy()[np.unique(rep)].sum()),
                             largest_group=int(np.bincount(rep).max()),
                             singletons=int((np.bincount(rep, minlength=len(ids))[np.unique(rep)] == 1).sum()),
                             unique_by_source=json.dumps(pd.Series(fam[np.unique(rep)]).value_counts().to_dict())))
            print(rows[-1], flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(D / "scan.tsv", sep="\t", index=False)
    tot = out.groupby("t")[["nodes", "unique"]].sum()
    print(tot.assign(compression=(tot.unique / tot.nodes).round(4)).to_string())


def apply(thr):
    D.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(gt.PROC / "PMA_motif_metadata.tsv", sep="\t", low_memory=False,
                     usecols=["pma_id", "source_db", "source_motif_id", "motif_tf_assignment"])
    uniq, mem = [], []
    for part in ("composite", "monomer"):
        ids, q, t, s = load(part)
        order, meta, nodes = priority(ids)
        rep = greedy(len(ids), q, t, s, thr, order)
        # s of each member to its representative (exact; reps have s=1 to self)
        sv = pd.Series(s, index=pd.MultiIndex.from_arrays([np.minimum(q, t), np.maximum(q, t)]))
        idx = np.arange(len(ids))
        a, b = np.minimum(idx, rep), np.maximum(idx, rep)
        s_rep = np.where(idx == rep, 1.0, sv.reindex(pd.MultiIndex.from_arrays([a, b])).to_numpy())
        r_ids = np.unique(rep)
        uid = {r: f"PMU_{part[0].upper()}{k + 1:06d}" for k, r in enumerate(sorted(r_ids, key=lambda r: ids[r]))}
        nm = pd.DataFrame({"node_id": ids, "unique_id": [uid[r] for r in rep], "representative_node": ids[rep],
                           "s_to_representative": s_rep, "partition": part})
        x = nodes.merge(nm, on="node_id").merge(md, on="pma_id")
        mem.append(x)
        g = x.groupby("unique_id")
        uniq.append(pd.DataFrame({
            "partition": part, "representative_node": g.representative_node.first(),
            "n_nodes": g.node_id.nunique(), "n_source_records": g.pma_id.size(),
            "sources": g.source_db.agg(lambda v: ";".join(f"{k}:{c}" for k, c in v.value_counts().items())),
            "tf_assignments": g.motif_tf_assignment.agg(lambda v: ";".join(sorted(set(v.dropna().astype(str))))[:500]),
            "min_s_to_representative": g.s_to_representative.min()}).reset_index())
    tag = f"{thr:g}"
    pd.concat(uniq).to_csv(D / f"PMA_unique_motifs_t{tag}.tsv", sep="\t", index=False, float_format="%.4f")
    pd.concat(mem).to_csv(D / f"PMA_motif_to_unique_t{tag}.tsv.gz", sep="\t", index=False, float_format="%.4f")
    print(pd.concat(uniq).groupby("partition").size().to_dict())


if __name__ == "__main__":
    scan() if sys.argv[1] == "scan" else apply(float(sys.argv[2]))
